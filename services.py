from flask import Flask, request
from flask_cors import CORS
from performance_util import get_perf_report, init

app = Flask(__name__)
CORS(app)
init(app)


@app.route("/performance_report_filter", methods=['POST'])
def _performance_filter():
    request_values = request.json
    data = get_perf_report(request_values)
    return data


if __name__ == "__main__":
    app.run('localhost', port=8085, debug=True)


