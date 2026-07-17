from flask import Flask

import config
from routes import register_blueprints

app = Flask(__name__)
register_blueprints(app)


if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.PORT, debug=config.FLASK_DEBUG)
