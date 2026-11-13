import os
import uuid
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    Response,
    send_file
)
from werkzeug.utils import secure_filename

from config import get_config
from services.db_service import (
    init_db,
    save_file_record,
    get_file_record,
    list_recent_files
)
from services.excel_service import (
    allowed_file,
    get_file_type,
    get_sheet_names,
    load_excel,
    export_dataframe_bytes
)
from services.analyzer import (
    detect_column_types,
    generate_kpis,
    generate_summary,
    get_column_information
)
from services.chart_service import create_charts


def create_app(config_object=None):
    """Application factory for AutoBI production service."""
    app = Flask(__name__)
    
    if config_object is None:
        config_object = get_config()
    app.config.from_object(config_object)

    # Ensure required directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["CACHE_FOLDER"], exist_ok=True)
    os.makedirs(app.config["DATA_FOLDER"], exist_ok=True)
    os.makedirs(os.path.dirname(app.config["LOG_FILE"]), exist_ok=True)

    # Configure structured logging
    log_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    file_handler = RotatingFileHandler(
        app.config["LOG_FILE"],
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    # Initialize SQLite metadata database
    init_db(app.config["DB_PATH"])
    app.logger.info("AutoBI initialized with metadata database at %s", app.config["DB_PATH"])

    # Security Headers Hook
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    # ------------------ ERROR HANDLERS ------------------
    @app.errorhandler(413)
    def file_too_large(error):
        app.logger.warning("Upload rejected: File exceeded MAX_CONTENT_LENGTH.")
        if request.is_json:
            return jsonify({"error": "File size exceeds the 50MB limit."}), 413
        return render_template(
            "error.html",
            error_code=413,
            error_title="File Too Large",
            error_message="The uploaded file exceeds the 50 MB maximum allowed size. Please upload a smaller file."
        ), 413

    @app.errorhandler(404)
    def not_found(error):
        if request.is_json:
            return jsonify({"error": "Resource not found."}), 404
        return render_template(
            "error.html",
            error_code=404,
            error_title="Page Not Found",
            error_message="The dashboard or resource you requested could not be found."
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("Internal Server Error: %s", error)
        if request.is_json:
            return jsonify({"error": "An unexpected internal server error occurred."}), 500
        return render_template(
            "error.html",
            error_code=500,
            error_title="Internal Server Error",
            error_message="We encountered an unexpected error processing your request. Please try again."
        ), 500

    # ------------------ ROUTES ------------------

    @app.route("/health")
    def health():
        """Health-check endpoint for load balancers and container monitors."""
        return jsonify({
            "status": "healthy",
            "service": "AutoBI",
            "environment": os.environ.get("FLASK_ENV", "production")
        }), 200

    @app.route("/")
    def index():
        """Landing page displaying upload interface and recent files."""
        recent = list_recent_files(app.config["DB_PATH"], limit=5)
        return render_template("index.html", recent_files=recent)

    @app.route("/upload", methods=["POST"])
    def upload():
        """Upload and parse Excel (.xlsx, .xls) or CSV files."""
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded."}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"error": "Please select a valid file."}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Unsupported file format. Please upload .xlsx, .xls, or .csv files."}), 400

        file_id = str(uuid.uuid4())
        raw_name = file.filename
        safe_name = secure_filename(raw_name) or f"upload_{file_id[:8]}.xlsx"
        stored_filename = f"{file_id}_{safe_name}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)

        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)
        except Exception as e:
            app.logger.error("Failed to save uploaded file: %s", e)
            return jsonify({"error": "Failed to store uploaded file on server."}), 500

        # Inspect and extract worksheet metadata
        try:
            sheet_names = get_sheet_names(file_path)
        except Exception as error:
            app.logger.warning("Failed to parse worksheets in %s: %s", file_path, error)
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"error": f"Unable to read file: {str(error)}"}), 400

        # Persist record in SQLite
        file_type = get_file_type(raw_name)
        save_file_record(
            db_path=app.config["DB_PATH"],
            file_id=file_id,
            original_name=raw_name,
            stored_filename=stored_filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            sheets=sheet_names
        )

        first_sheet = sheet_names[0]
        return redirect(url_for("dashboard", file_id=file_id, sheet=first_sheet))

    @app.route("/dashboard/<file_id>")
    def dashboard(file_id):
        """Render interactive dashboard for a specific file and worksheet."""
        file_info = get_file_record(app.config["DB_PATH"], file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            app.logger.warning("Dashboard requested for non-existent file_id: %s", file_id)
            return redirect(url_for("index"))

        selected_sheet = request.args.get("sheet", file_info["sheets"][0])
        if selected_sheet not in file_info["sheets"]:
            selected_sheet = file_info["sheets"][0]

        try:
            df = load_excel(
                file_path=file_info["path"],
                sheet_name=selected_sheet,
                file_id=file_id,
                cache_folder=app.config["CACHE_FOLDER"]
            )
        except Exception as error:
            app.logger.error("Error loading worksheet %s for file %s: %s", selected_sheet, file_id, error)
            return render_template(
                "error.html",
                error_code=500,
                error_title="Worksheet Read Error",
                error_message=f"Could not load data from worksheet '{selected_sheet}': {str(error)}"
            ), 500

        column_types = detect_column_types(df)
        kpis = generate_kpis(df, column_types)
        summary = generate_summary(df, column_types)
        charts = create_charts(df, column_types)
        column_info = get_column_information(df)

        # Categorical Filter Extraction (limit to top unique categories)
        filters = {}
        for column in column_types["categorical"][:6]:
            unique_values = (
                df[column]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
            if 0 < len(unique_values) <= app.config["MAX_FILTER_UNIQUE_VALUES"]:
                filters[column] = sorted(unique_values)

        # Data preview preparation
        preview_limit = app.config.get("PREVIEW_ROWS_LIMIT", 500)
        preview_df = df.head(preview_limit).copy()
        for col in preview_df.columns:
            if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
                preview_df[col] = preview_df[col].dt.strftime("%Y-%m-%d")

        preview_data = preview_df.fillna("").to_dict(orient="records")

        return render_template(
            "dashboard.html",
            file_id=file_id,
            filename=file_info["original_name"],
            sheets=file_info["sheets"],
            selected_sheet=selected_sheet,
            kpis=kpis,
            charts=charts,
            summary=summary,
            filters=filters,
            columns=list(df.columns),
            column_info=column_info,
            preview_data=preview_data
        )

    @app.route("/api/filter/<file_id>", methods=["POST"])
    def filter_dashboard(file_id):
        """Asynchronous API endpoint to filter data and return recalculated metrics and charts."""
        file_info = get_file_record(app.config["DB_PATH"], file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            return jsonify({"error": "File session expired or not found."}), 404

        payload = request.get_json(silent=True) or {}
        sheet = payload.get("sheet", file_info["sheets"][0])
        selected_filters = payload.get("filters", {})

        try:
            df = load_excel(
                file_path=file_info["path"],
                sheet_name=sheet,
                file_id=file_id,
                cache_folder=app.config["CACHE_FOLDER"]
            )
        except Exception as error:
            app.logger.error("Filter read failure for file %s: %s", file_id, error)
            return jsonify({"error": f"Failed to reload sheet: {str(error)}"}), 500

        # Apply multi-select categorical filters defensively
        for column, selected_values in selected_filters.items():
            if column in df.columns and isinstance(selected_values, list) and selected_values:
                df = df[df[column].astype(str).isin([str(v) for v in selected_values])]

        column_types = detect_column_types(df)
        kpis = generate_kpis(df, column_types)
        charts = create_charts(df, column_types)
        summary = generate_summary(df, column_types)

        return jsonify({
            "kpis": kpis,
            "charts": charts,
            "summary": summary
        })

    @app.route("/api/export/<file_id>")
    def export_data(file_id):
        """Export filtered or complete worksheet data as CSV or XLSX."""
        file_info = get_file_record(app.config["DB_PATH"], file_id)
        if not file_info or not os.path.exists(file_info["path"]):
            return jsonify({"error": "File not found."}), 404

        sheet = request.args.get("sheet", file_info["sheets"][0])
        export_fmt = request.args.get("format", "csv").lower()

        try:
            df = load_excel(
                file_path=file_info["path"],
                sheet_name=sheet,
                file_id=file_id,
                cache_folder=app.config["CACHE_FOLDER"]
            )
        except Exception as error:
            return jsonify({"error": str(error)}), 500

        bytes_data, mimetype, ext = export_dataframe_bytes(df, file_format=export_fmt)
        out_filename = f"{Path(file_info['original_name']).stem}_{sheet}_export.{ext}"

        return Response(
            bytes_data,
            mimetype=mimetype,
            headers={
                "Content-Disposition": f"attachment; filename=\"{out_filename}\""
            }
        )

    return app


# Application instance for WSGI servers
app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("DEBUG", "True").lower() in ("true", "1")
    )
