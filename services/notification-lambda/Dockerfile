FROM public.ecr.aws/lambda/python:3.11

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN pip install -r ${LAMBDA_TASK_ROOT}/requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy Lambda function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set handler
CMD [ "lambda_function.lambda_handler" ]
