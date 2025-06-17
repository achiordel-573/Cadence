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
def create_parallax_video(image_path, params, animation=None):
    duration = params["duration"] or "10"
    framerate = params["framerate"] or "60"
    height = params["height"] or "1080"
    width = params["width"] or "1920"

    output_video = f"static/output_{uuid.uuid4()}.mp4"

    if animation and animation["animation_type"] == "circle":
        try:
            command = ["depthflow",
                        "input", "-i", image_path,
                        "circle", 
                        "--intensity", animation["intensity"],
                        "--reverse", f"--{animation["reverse"]}",
                        "--cumulative", f"--{animation["cumulative"]}",
                        "--smooth", f"--{animation["smooth"]}",
                        "--isometric", animation["isometric"],
                        "--steady", animation["steady"],
                        "main",
                        "-o", output_video]
            subprocess.run(command, check=True)
            return output_video
        except subprocess.CalledProcessError as e:
            return f"Error: {e}"
    else:
        try:
            command = ["depthflow",
                        "input", "-i", image_path, 
                        "main", 
                        "--time", duration, 
                        "--fps", framerate, 
                        "--height", height, 
                        "--width", width,  
                        "-o", output_video]
            subprocess.run(command, check=True)
            return output_video
        except subprocess.CalledProcessError as e:
            return f"Error: {e}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/api/create_video', methods=['POST'])
def create_video():
    print(request.form)
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    params = {
        "duration": None if request.form["duration"] == "" else request.form["duration"],
        "framerate": None if request.form["framerate"] == "" else request.form["framerate"],
        "height": None if request.form["height"] == "" else request.form["height"],
        "width": None if request.form["width"] == "" else request.form["width"]
    }

    if request.form.get("animation_type", None):
        animation_params = {
            "animation_type": None or request.form["animation_type"],
            "cumulative": None or request.form["cumulative"],
            "reverse": None or request.form["reverse"],
            "smooth": None or request.form["smooth"],
            "isometric": None or request.form["isometric"],
            "intensity": None or request.form["intensity"],
            "steady": None or request.form["steady"],
            "isLooped": None or request.form["looped"],
        }
    else:
        animation_params = None
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    image_path = f'temp/temp_{uuid.uuid4()}.jpg'
    image.save(f'{image_path}')

    task = create_parallax_video.delay(image_path, params, animation_params)
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