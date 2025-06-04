from celery import Celery
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import os, uuid, subprocess

app = Flask(__name__)
cors = CORS(app)
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task
def create_parallax_video(image_path):
    try:
        output_video = f"static/output_{uuid.uuid4()}.mp4"
        command = ["depthflow", "input", "-i", image_path, "main",  "-o", output_video]
        subprocess.run(command, check=True)
        return output_video
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/api/create_video', methods=['POST'])
def create_video():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    image_path = f'temp/temp_{uuid.uuid4()}.jpg'
    image.save(f'{image_path}')

    task = create_parallax_video.delay(image_path)
    return jsonify({'task_id': task.id}), 202

@app.route("/api/task_status/<task_id>", methods=['GET'])
def task_status(task_id):
    task = celery.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': task.result,
        }
    else:
        # Something wrong
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

if __name__ == "__main__":
    app.run(port=64005, debug=True)