# Use AWS Lambda Python runtime for x86_64 architecture
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.11

# Copy requirements file with AI dependencies
COPY requirements-lambda-minimal.txt ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN pip install --no-cache-dir -r requirements-lambda-minimal.txt

# Copy application code
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Set the Lambda handler
CMD ["app.main.lambda_handler"]