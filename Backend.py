from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import boto3
from bs4 import BeautifulSoup
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client
from gtts import gTTS
import os
import uuid
import pythoncom  # Required to initialize COM on Windows
import time

app = Flask(__name__)
CORS(app)


def calculate_bmi(weight, height):
    """Calculate the Body Mass Index (BMI)."""
    return weight / (height ** 2)

def categorize_bmi(bmi):
    """Categorize the BMI based on standard BMI categories."""
    if bmi < 18.5:
        return "Underweight"
    elif 18.5 <= bmi < 24.9:
        return "Normal weight"
    elif 25 <= bmi < 29.9:
        return "Overweight"
    else:
        return "Obesity"

@app.route('/calculate_bmi', methods=['POST'])
def index():
    try:
        weight = float(request.form['weight'])
        height = float(request.form['height'])
        bmi = calculate_bmi(weight, height)
        category = categorize_bmi(bmi)
        return jsonify({"bmi": round(bmi, 2), "category": category})
    except ValueError:
        return jsonify({"error": "Invalid input. Please enter numerical values."}), 400

@app.route('/send_bulk_email', methods=['POST'])
def send_bulk_email():
    try:
        # Get the form data
        subject = request.form['subject']
        body = request.form['body']
        recipients = request.form['recipients'].split(',')  # Split comma-separated emails

        # Sender email and password
        sender_email = "Enter your Email"  # Replace with your email
        password = "Enter your password"  # Replace with your app-specific password

        # Set up the SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)

        # Email subject and message body
        email_body = f"Subject: {subject}\n\n{body}"

        # Send email to each recipient
        for receiver_email in recipients:
            server.sendmail(sender_email, receiver_email.strip(), email_body)

        server.quit()

        return "Bulk emails sent successfully!"
    except smtplib.SMTPAuthenticationError:
        return render_template_string("<h1>Failed to authenticate. Check your email and password.</h1>"), 401
    except Exception as e:
        return render_template_string(f"<h1>An error occurred: {e}</h1>"), 500


@app.route('/send_email', methods=['POST'])
def send_email():
    try:
        # Get form data
        sender_email = request.form['sender_email']
        password = request.form['password']
        subject = request.form['subject']
        body = request.form['body']
        recipients = request.form['recipients']

        # Prepare email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipients
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Send email via SMTP server (example using Gmail)
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, recipients.split(','), msg.as_string())
        server.quit()

        return jsonify({"message": "Email sent successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def get_geo_coordinates():
    try:
        # Make a request to the ipinfo API
        response = requests.get('https://ipinfo.io')
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the JSON response
        data = response.json()

        # Extract the coordinates
        location = data.get('loc', '')
        latitude, longitude = location.split(',')

        return float(latitude), float(longitude)
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None, None

@app.route('/get_coordinates', methods=['GET'])
def get_coordinates():
    latitude, longitude = get_geo_coordinates()
    if latitude is not None and longitude is not None:
        return jsonify({'latitude': latitude, 'longitude': longitude})
    else:
        return jsonify({'error': 'Could not retrieve geo coordinates.'}), 500

def get_location():
    try:
        # Make a request to the ipinfo API
        response = requests.get('https://ipinfo.io')
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the JSON response
        data = response.json()

        # Extract relevant details
        ip = data.get('ip', 'N/A')
        city = data.get('city', 'N/A')
        region = data.get('region', 'N/A')
        country = data.get('country', 'N/A')
        location = data.get('loc', 'N/A').split(',')
        latitude = location[0] if len(location) > 0 else 'N/A'
        longitude = location[1] if len(location) > 1 else 'N/A'

        return {
            'IP': ip,
            'City': city,
            'Region': region,
            'Country': country,
            'Latitude': latitude,
            'Longitude': longitude
        }

    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

@app.route('/get-location', methods=['GET'])
def location_api():
    location = get_location()
    if location:
        return jsonify(location)
    else:
        return jsonify({"error": "Could not retrieve location data."}), 500

@app.route('/launch', methods=["POST"])
def launch_ec2_instance():
    # Retrieve parameters from POST request
    x = request.form.get('instance_type')
    y = request.form.get('instance_id')
    z = request.form.get('regional_name')
    a = request.form.get('access_key')
    b = request.form.get('secret_key')

    # Connect to EC2
    ec2 = boto3.resource(
        service_name="ec2",
        region_name=z,
        aws_access_key_id=a,
        aws_secret_access_key=b
    )

    # Launch instance
    instance = ec2.create_instances(
        ImageId=y, 
        InstanceType=x,         
        MinCount=1,                      
        MaxCount=1                       
    )

    return "Instance launched successfully!"

def google_search(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    query = query.replace(' ', '+')
    url = f"https://www.google.com/search?q={query}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print("Failed to retrieve page")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    
    results = []
    
    for g in soup.find_all('div', class_='g', limit=5):
        title_element = g.find('h3')
        link_element = g.find('a')
        snippet_element = g.find('span', class_='aCOpRe')

        if title_element and link_element:
            title = title_element.get_text()
            link = link_element['href']
            
            if link.startswith('/url?q='):
                link = link.split('/url?q=')[1].split('&')[0]

            snippet = snippet_element.get_text() if snippet_element else ""

            results.append({"title": title, "link": link, "snippet": snippet})

    return results

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get('query')
    if not query:
        return jsonify({"error": "Query is required"}), 400
    
    results = google_search(query)
    return jsonify(results)

scheduler = BackgroundScheduler()
scheduler.start()

# Email sending function
def send_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Create server object with SSL option
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        # Login credentials for sending the mail
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
        print(f"Email sent to {recipient_email}")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

# Schedule email function
def schedule_email(sender_email, sender_password, recipient_email, subject, body, schedule_day, schedule_time):
    day_map = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }

    current_day = datetime.datetime.today().weekday()
    target_day = day_map[schedule_day.lower()]
    
    # Calculate the number of days to wait
    days_until_target = (target_day - current_day) % 7
    schedule_datetime = datetime.datetime.now() + datetime.timedelta(days=days_until_target)
    
    # Set the time of the email
    hour, minute = map(int, schedule_time.split(':'))
    schedule_datetime = schedule_datetime.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    scheduler.add_job(send_email, 'date', run_date=schedule_datetime, args=[sender_email, sender_password, recipient_email, subject, body])

@app.route('/schedule_email', methods=['POST'])
def schedule_email_route():
    try:
        data = request.get_json()

        sender_email = data['sender_email']
        sender_password = data['sender_password']
        recipient_email = data['recipient_email']
        subject = data['subject']
        body = data['body']
        schedule_day = data['schedule_day']
        schedule_time = data['schedule_time']

        schedule_email(sender_email, sender_password, recipient_email, subject, body, schedule_day, schedule_time)

        return jsonify({"message": "Email scheduled successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/set-volume', methods=['POST'])
def set_volume():
    try:
        # Initialize COM library for this thread
        pythoncom.CoInitialize()

        # Extract the volume level from the form data
        volume_level = request.form.get('volume', type=int)
        
        if volume_level is None:
            raise ValueError("No volume level provided")

        # Set the system volume using a Windows-specific command or library
        # Example using `pycaw` library (you may need to install this via pip):
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        # Set the volume (the value should be between 0.0 and 1.0)
        volume.SetMasterVolumeLevelScalar(volume_level / 100.0, None)

        return jsonify({"success": True, "volume": volume_level})

    except Exception as e:
        # Log the error and return a 500 status code
        print(f"Error setting volume: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        # Uninitialize COM library for this thread
        pythoncom.CoUninitialize()

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    data = request.get_json()
    text = data['text']
    
    if text.strip() == "":
        return jsonify({"error": "No text provided"}), 400

    # Generate the TTS file
    try:
        tts = gTTS(text=text, lang='en')
        filename = f"speech_{int(time.time())}.mp3"  # Create a unique filename using a timestamp
        filepath = os.path.join('static', filename)
        tts.save(filepath)

        return jsonify({"speech_url": f"/static/{filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    # Ensure the 'static/audio' directory exists
    os.makedirs(os.path.join('static', 'audio'), exist_ok=True)
    
if __name__ == "__main__":
    app.run(port=5000, host='0.0.0.0')
