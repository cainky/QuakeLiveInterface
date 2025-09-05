from flask import Flask, render_template, request
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run():
    app.logger.info('Received form data: %s', request.form)
    return "Check the server log for the form data."

if __name__ == '__main__':
    app.run()
