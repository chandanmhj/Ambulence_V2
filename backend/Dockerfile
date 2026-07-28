FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Train the ML models at image build time so they're ready on first run.
RUN python ml_models/generate_synthetic_data.py && \
    python ml_models/train_eat_model.py && \
    python ml_models/train_clear_time_model.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
