# QnA Pair Generator Web App (Flask)
# Browser-based GUI for uploading text files and generating CSV output

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
import os
import csv
import json
import tempfile
import threading
import queue
import time
import qna_bm_core
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Global queue for progress updates
progress_queue = queue.Queue()

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate_qa():
    """Process uploaded file and generate Q&A pairs with live progress"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.txt'):
            return jsonify({'error': 'Only .txt files are supported'}), 400
        
        # Get all settings from request (capture before background thread)
        max_pairs = int(request.form.get('max_pairs', 100))
        skip_review = request.form.get('skip_review', 'true').lower() == 'true'
        
        # Read file content
        file_content = file.read().decode('utf-8')
        source_name = secure_filename(file.filename)
        
        # Clear progress queue
        while not progress_queue.empty():
            try:
                progress_queue.get_nowait()
            except:
                pass
        
        def generate_with_progress():
            """Generate Q&A pairs and send progress updates"""
            pairs = []
            
            def progress_callback(message):
                """Callback to send progress updates"""
                progress_queue.put({
                    'type': 'progress',
                    'message': message
                })
            
            try:
                # Process the file with progress callback
                pairs = qna_bm_core.process_text_file(
                    file_content,
                    source_name,
                    max_pairs=max_pairs,
                    progress_callback=progress_callback,
                    skip_review=skip_review,
                    max_workers=10  # Increase workers for faster processing
                )
                
                # Send completion
                progress_queue.put({
                    'type': 'complete',
                    'pairs': pairs,
                    'count': len(pairs)
                })
            except ValueError as e:
                # Handle API errors specifically
                error_msg = str(e)
                progress_queue.put({
                    'type': 'error',
                    'error': error_msg,
                    'is_rate_limit': 'rate limit' in error_msg.lower(),
                    'is_auth_error': 'invalid api key' in error_msg.lower()
                })
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"Error in generation: {error_details}")
                progress_queue.put({
                    'type': 'error',
                    'error': f"{str(e)}\n\nCheck server logs for details."
                })
        
        # Start generation in background thread
        thread = threading.Thread(target=generate_with_progress)
        thread.daemon = True
        thread.start()
        
        # Return streaming response
        def event_stream():
            while True:
                try:
                    # Get progress update with timeout
                    data = progress_queue.get(timeout=1)
                    
                    if data['type'] == 'complete':
                        yield f"data: {json.dumps(data)}\n\n"
                        break
                    elif data['type'] == 'error':
                        yield f"data: {json.dumps(data)}\n\n"
                        break
                    else:
                        yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    continue
        
        return Response(stream_with_context(event_stream()), mimetype='text/event-stream')
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-csv', methods=['POST'])
def download_csv():
    """Generate and download CSV file"""
    try:
        data = request.json
        pairs = data.get('pairs', [])
        
        if not pairs:
            return jsonify({'error': 'No data to export'}), 400
        
        # Create temporary CSV file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
        
        writer = csv.writer(temp_file)
        # Write header
        writer.writerow(['Question', 'Answer', 'Source'])
        # Write data
        for pair in pairs:
            writer.writerow([
                pair['question'],
                pair['answer'],
                pair['source']
            ])
        
        temp_file.close()
        
        return send_file(
            temp_file.name,
            mimetype='text/csv',
            as_attachment=True,
            download_name='qa_bm_pairs.csv'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Check if API is configured"""
    has_config = bool(qna_bm_core.API_KEY and qna_bm_core.BASE_URL)
    return jsonify({
        'configured': has_config,
        'model_gen': qna_bm_core.MODEL_GEN,
        'model_review': qna_bm_core.MODEL_REVIEW
    })

@app.route('/api/verify-connection', methods=['GET'])
def verify_connection():
    """Verify AI API connection by making a test call"""
    try:
        if not qna_bm_core.API_KEY or not qna_bm_core.BASE_URL:
            return jsonify({
                'connected': False,
                'error': 'API credentials not configured'
            })
        
        # Make a simple test call
        test_response = qna_bm_core.chat(
            qna_bm_core.MODEL_GEN,
            "You are a helpful assistant.",
            "Say 'OK' if you can read this.",
            temperature=0.1
        )
        
        if test_response and len(test_response) > 0:
            return jsonify({
                'connected': True,
                'model': qna_bm_core.MODEL_GEN,
                'message': 'Successfully connected to AI API'
            })
        else:
            return jsonify({
                'connected': False,
                'error': 'No response from API'
            })
    except ValueError as e:
        # Handle specific API errors
        error_msg = str(e)
        return jsonify({
            'connected': False,
            'error': error_msg,
            'is_rate_limit': 'rate limit' in error_msg.lower(),
            'is_auth_error': 'invalid api key' in error_msg.lower()
        }), 200
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 200

if __name__ == '__main__':
    # Check if API is configured
    if not qna_bm_core.API_KEY or not qna_bm_core.BASE_URL:
        print("\n" + "="*60)
        print("WARNING: API credentials not configured!")
        print("Please set OPENAI_API_KEY and OPENAI_BASE_URL in your .env file")
        print("="*60 + "\n")
    
    # Try port 8080 first, fallback to 5001 if needed
    port = 8080
    print("Starting QnA Pair Generator Web App...")
    print(f"Open your browser and navigate to: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)

