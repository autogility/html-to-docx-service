import os
import json
import subprocess
import tempfile
import logging
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the Node.js converter script
CONVERTER_SCRIPT = '/app/convert.js'


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "html-to-docx"}), 200


@app.route('/convert/docx', methods=['POST'])
def convert_to_docx():
    try:
        content_type = request.content_type or ''

        if 'application/json' in content_type:
            data     = request.get_json(force=True)
            html     = data.get('html', '')
            filename = data.get('filename', 'document.docx')
        else:
            html     = request.data.decode('utf-8')
            filename = request.headers.get('X-Filename', 'document.docx')

        if not html.strip():
            return jsonify({"error": "No HTML content provided"}), 400

        if not filename.endswith('.docx'):
            filename = filename.replace('.pdf', '').replace('.txt', '') + '.docx'

        logger.info(f"Converting HTML → DOCX | file: {filename} | size: {len(html)} chars")

        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = os.path.join(tmpdir, 'input.html')
            docx_path = os.path.join(tmpdir, 'output.docx')

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            # Call Node.js html-to-docx converter
            result = subprocess.run(
                ['node', CONVERTER_SCRIPT, html_path, docx_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=tmpdir
            )

            logger.info(f"Node stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"Node stderr: {result.stderr}")

            if result.returncode != 0 or not os.path.exists(docx_path):
                files = os.listdir(tmpdir)
                logger.error(f"Conversion failed. Files in tmpdir: {files}")
                return jsonify({
                    "error": "Output file not created",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "files": files
                }), 500

            size = os.path.getsize(docx_path)
            logger.info(f"DOCX created: {size} bytes")

            return send_file(
                docx_path,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                as_attachment=True,
                download_name=filename
            )

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Conversion timed out (60s)"}), 504
    except Exception as e:
        logger.exception("Unexpected error")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False)
