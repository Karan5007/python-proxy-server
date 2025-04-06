# Use the official Python image as the base image
FROM python:3.12-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code into the container
COPY src/ .

# Expose the port the app runs on
EXPOSE 8888

# Command to run the application
CMD ["python", "proxy.py"]

# CMD ["python", "proxy.py", "120"]