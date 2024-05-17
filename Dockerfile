# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app/
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /usr/src/app/
COPY . .

# Make port 8443 available to the world outside this container (if you're using webhooks)
EXPOSE 8443

# Define environment variable
ENV TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ENV MONGO_URI=mongodb://your_mongodb_uri

# Run app.py when the container launches
CMD ["python", "./telegram_bot.py"]
