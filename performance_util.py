from database_util import get_service_collection, get_master_collection
import pymongo
from flask import jsonify
import logging
import requests, json
from consul_util import get_config_value
from elasticapm.contrib.flask import ElasticAPM
import configparser

logging.basicConfig(filename='./log/app.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read("config.ini")

auth_token = config.get("credentials", "auth_token")
user_id = config.get("credentials", "user_id")

def get_perf_report(request):
    try:
        service_details = _find_service_url("performance")

        if request is None:
            required_entities = _fetch_required_entities(service_details)
            if not bool(required_entities):
                data = _call_perf_report(None)
            else:
                data = {}
                logger.info("Mandatory entities required  : " + required_entities)
        else:
            input_val = request.split(";")
            if "release" or "performance" in input_val[0]:
                service_input = str(input_val[0].split(" ")[1]).replace("_", ".")+ "_" + input_val[1]
            else:
                service_input = input_val[1]
            if "report" in request:
                data = _call_perf_report(service_input)
            else:
                # if request_values.count("release") == 1:
                perf_result = _get_perf_data(service_details, service_input)
                data = perf_result
                data = jsonify(data)
    except Exception as e:
        logger.error("Exception in  _performance_filter : " + str(e))
        data = {"success": "", "data": {}, "error": {"Message": str(e)}}
        data = jsonify(data)
    return data


def _fetch_required_entities(service_details):
    """Checks if any entity is set required, if set as required then return it"""
    try:
        required_entities = {}
        for entity in service_details:
            if "true" == service_details[entity]["required"]:
                required_entities[entity] = entity
    except Exception as e:
        logger.error("Exception in  _fetch_required_entities : " + str(e))
    return required_entities


def _call_perf_report(query):
    """If release is given then compare it with the default configured in mongo db ,
    if not then compare latest with previous"""
    try:
        service_details = _find_service_url("performance")
        if query is None:
            url = service_details["report_url"] + _find_latest()
        else:
            url = service_details["report_url"] + _compare_url(query, service_details["baseline"])

        resp = requests.get(url=url.strip(), params=None)

        if "error" in resp.text.lower():
            data = {"data": None}
        else:
            data = {"data": {"url": url}}

    except Exception as e:
        logger.error("Exception in  _call_perf_report : " + str(e))
        data = None
    if data is not None:
        data = jsonify(data)
    return data


def _find_latest():
    """finds latest and second latest release"""
    try:
        db = get_master_collection()
        service_details = db.find({"master.key": "perf"}).sort([("master.value", pymongo.DESCENDING)]).limit(1)
        first = 1
        for service in service_details:
            for release in sorted(service["master"]["value"], reverse=True):
                if first == 2:
                    second_latest = release
                else:
                    latest_release = release
                    first = 2
                break
            break

        latest_rel_num = str(latest_release).replace("_", ".")
        latest = str("/"+second_latest+"/"+latest_rel_num)
    except Exception as e:
        logger.error("Exception in  _find_latest : " + str(e))
    return latest


def _compare_url(release_input, default_baseline):
    """compares given release with the default release mentioned in database"""
    try:
        if "." not in release_input:
            release_input = str(release_input).replace("_", ".")
        baseline = "/" + str(default_baseline) + "/" + release_input
    except Exception as e:
        logger.error("Exception in  _compare_with : " + str(e))
    return baseline


def _find_service_url(keyword):
    """find microservice endpoint url's and return"""
    try:
        db = get_service_collection()
        result = db.find({"name": keyword})
        service_endpoint = {}
        for item in result:
            service_endpoint["service_url"] = item["value"]["url"]["service_url"]
            service_endpoint["report_url"] = item["value"]["url"]["report_url"]
            service_endpoint["baseline"] = item["value"]["entities"]["release"]["default"]
            service_endpoint["entities"] = item["value"]["entities"]
            service_endpoint["threshold"] = item["value"]["failure_threshold"]
            break
    except Exception as e:
        logger.error("Exception in  _find_service_url : " + str(e))
    return service_endpoint


def _call_rest_api(url, input_data, request_type):
    """Calls the other rest api's"""
    try:
        if request_type == 'post':
            req = requests.post(url, params=input_data, json=input_data)
        else:
            req = requests.get(url, params=input_data)
        response = req.text
        val = json.loads(response)
    except Exception as e:
        logger.error("Exception in _call_rest_api : " + str(e))
        raise ValueError("Filter is down!!!!")
    return val


def _get_perf_data(service_details, service_input):
    try:
        service_input_json = _service_input_json(auth_token, user_id, service_details["baseline"], service_input)
        perf_data = _call_rest_api(service_details["service_url"], service_input_json, 'post')
        perf_data = perf_data["data"]
        failure_count = 0
        success_count = 0
        link = service_details['report_url']+'/'+perf_data['perf']['Baseline_Release']+'/'+perf_data['perf']['Current_Release']
        if perf_data is not None:
            result = perf_data["perf"]["result"]
            state_index = (result[0]).index("Status")
            for data in result:
                if "Pass" == data[state_index]:
                    success_count = int(success_count) + 1
                else:
                    failure_count = int(failure_count) + 1
        failure_percent = ((failure_count - 1) / (len(result)-1)) * 100

        if failure_percent > int(service_details["threshold"]):
            perf_result = _perf_result(perf_data, success_count, failure_count, "Failed", service_input,link)
        else:
            perf_result = _perf_result(perf_data, success_count, failure_count, "Passed", service_input,link)
        print(perf_result)
    except Exception as e:
        logger.error("Exception in  _get_perf_data : " + str(e))
    return perf_result


def _perf_result(perf_data, success_count, failure_count, result, service_input,link):
    perf_result = {"success": "true",
                   "data": {"Result": result, "Current Release": service_input,
                            "Baseline Release": perf_data["perf"]["Baseline_Release"],
                            "Success": success_count, "Failure": failure_count,"report_url":link}, "error": {}}
    return perf_result


def _service_input_json(auth_token, user_id, baseline, current_release):
    if "." not in current_release:
        current_release = current_release.replace("_", ".")
    input_json = {
            "authheader": {
                "authtoken": auth_token,
                "userid": user_id
            },
            "data": {
                "baseline_release": baseline.strip(),
                "current_release": current_release.strip()
            }
        }
    return input_json


def init(app):
    apm = None
    logger.info("ENABLE_APM" + str(get_config_value('ENABLE_APM')))
    logger.info("APM_SERVER_URL" + str(get_config_value('APM_SERVER_URL')))
    if get_config_value('ENABLE_APM') is not None and 'Y' in str(get_config_value('ENABLE_APM')):
        logger.info("APM Enabled")
        app.config['ELASTIC_APM'] = {
            'SERVICE_NAME': 'performancefilter',
            'SERVER_URL': get_config_value('APM_SERVER_URL').decode(encoding="utf-8"),
            'DEBUG': True
        }
        apm = ElasticAPM(app)
    return apm

