"""
Flask API — receives CSV params from frontend, runs Grasshopper compute jobs.

RESPONSIBILITY: routes, status codes, JSON responses only.
  - Does NOT call Rhino.Compute directly → that is compute_service.py
  - Does NOT read .gh files → paths come from config.py

ROUTE LAYOUT:
  /definitions/<id>/...     — one Grasshopper file per id (see config.DEFINITIONS)
  /solve, /definition-defaults — legacy aliases for DEFAULT_DEFINITION_ID (joint-wiz)

Run: pipenv run dev   or   pipenv run python app.py
"""

from flask import Flask, current_app, jsonify, request

import config
from api_helpers import (
    format_solve_job_response,
    normalize_csv_analyze_result,
    parse_input_lists,
    parse_solve_request,
)
from compute_service import ComputeService, ComputeServiceError, create_service
from llm import BoxCommandParser, CSVAnalyzer, analyze_image


def create_app() -> Flask:
    """Build Flask app and wire routes. Called once at import and by tests."""
    app = Flask(__name__)

    compute_service: ComputeService = create_service()
    app.config["COMPUTE_SERVICE"] = compute_service

    @app.errorhandler(ComputeServiceError)
    def handle_compute_error(exc: ComputeServiceError):
        return jsonify({"error": str(exc)}), 500

    @app.errorhandler(ValueError)
    @app.errorhandler(TypeError)
    def handle_bad_request(exc: Exception):
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(config.DefinitionNotFoundError)
    def handle_definition_not_found(exc: config.DefinitionNotFoundError):
        return jsonify({"error": f'Unknown definition "{exc.args[0]}"'}), 404

    @app.errorhandler(config.DefinitionNotEnabledError)
    def handle_definition_not_enabled(exc: config.DefinitionNotEnabledError):
        return jsonify({"error": str(exc)}), 501

    def service() -> ComputeService:
        return current_app.config["COMPUTE_SERVICE"]

    @app.get("/health")
    def health():
        """Ping + list each definition file found on disk."""
        return jsonify({"status": "ok", "service": service().healthcheck()})

    @app.get("/definitions")
    def list_definitions():
        return jsonify(
            {
                "defaultDefinitionId": config.DEFAULT_DEFINITION_ID,
                "definitions": [
                    config.definition_public_dict(definition_id)
                    for definition_id in config.list_definition_ids()
                ],
            }
        )

    @app.get("/definitions/<definition_id>/definition-defaults")
    def get_definition_defaults(definition_id: str):
        params = service().get_definition_default_params(definition_id)
        return jsonify({"definitionId": definition_id, "params": params})

    @app.post("/definitions/<definition_id>/solve")
    def start_definition_solve(definition_id: str):
        spec = config.get_definition(definition_id)
        config.require_definition_enabled(spec)
        input_lists, variation_indices, quantities = parse_solve_request(
            request.get_json(silent=True) or {}
        )
        job_id = service().start_job(spec["id"], input_lists, variation_indices, quantities)
        return (
            jsonify(
                {
                    "jobId": job_id,
                    "definitionId": spec["id"],
                    "status": "running",
                    "stage": spec["stage"],
                }
            ),
            202,
        )

    @app.get("/definitions/<definition_id>/solve/<job_id>")
    def get_definition_solve(definition_id: str, job_id: str):
        spec = config.get_definition(definition_id)
        job = service().get_job(job_id, definition_id=spec["id"])
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(format_solve_job_response(job, spec))

    @app.get("/definition-defaults")
    def legacy_definition_defaults():
        return get_definition_defaults(config.DEFAULT_DEFINITION_ID)

    @app.post("/solve")
    def legacy_start_solve():
        return start_definition_solve(config.DEFAULT_DEFINITION_ID)

    @app.get("/solve/<job_id>")
    def legacy_get_solve(job_id: str):
        return get_definition_solve(config.DEFAULT_DEFINITION_ID, job_id)

    @app.post("/csv/analyze")
    def analyze_csv():
        body = request.get_json(silent=True) or {}
        csv_text = body.get("csvText", "")
        if not csv_text.strip():
            return jsonify({"error": "Empty CSV"}), 400

        result = normalize_csv_analyze_result(CSVAnalyzer().analyze(csv_text))
        return jsonify(
            {
                "inputLists": result["inputLists"],
                "variationNames": result["variationNames"],
                "variationCount": result["variationCount"],
            }
        )

    @app.post("/image/analyze")
    def analyze_image_route():
        body = request.get_json(silent=True) or {}
        image_b64 = body.get("imageBase64", "")
        media_type = body.get("mediaType", "")
        if not image_b64.strip() or not media_type.strip():
            return jsonify({"error": "Empty image"}), 400

        result = normalize_csv_analyze_result(analyze_image(image_b64, media_type))
        return jsonify(
            {
                "inputLists": result["inputLists"],
                "variationNames": result["variationNames"],
                "variationCount": result["variationCount"],
            }
        )

    @app.post("/chat/command")
    def parse_chat_command():
        body = request.get_json(silent=True) or {}
        message = body.get("message", "")
        if not message.strip():
            return jsonify({"error": "Empty message"}), 400

        existing_boxes = body.get("existingBoxes", [])
        if not isinstance(existing_boxes, list):
            return jsonify({"error": '"existingBoxes" must be an array'}), 400

        command = BoxCommandParser().parse(message, existing_boxes)

        if command.get("action") == "add" and command.get("add"):
            add = command["add"]
            normalized = normalize_csv_analyze_result(
                {
                    "inputLists": add.get("inputLists") or {},
                    "variationNames": add.get("variationNames") or [],
                }
            )
            command["add"] = {
                "inputLists": normalized["inputLists"],
                "variationNames": normalized["variationNames"],
                "variationCount": normalized["variationCount"],
            }

        if command.get("action") == "update":
            for key in ("fields", "fieldDeltas"):
                raw_map = command.get(key)
                if not raw_map:
                    continue
                coerced: dict[str, int] = {}
                for name in config.CSV_GH_INPUT_NAMES:
                    raw = raw_map.get(name)
                    if raw is None:
                        continue
                    try:
                        coerced[name] = int(round(float(raw)))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f'"{name}" must be a number') from exc
                command[key] = coerced

        return jsonify(command)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=config.FLASK_HOST, port=config.PORT, debug=config.FLASK_DEBUG)
