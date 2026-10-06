## Generate a Gemini API Key

This project requires a Google Gemini API key.

## Build and Run

### 1. Clone the repository

```powershell
git clone https://github.com/ptomaszewski29/HumanInTheLoop.git
cd HumanInTheLoop
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Configure environment variables

### Steps

1. Open [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Navigate to **API Keys**.
4. Click **Create API Key**.
5. Copy the generated key.

Create a `.env` file in the project root and add:

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Example:

```env
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Verify Configuration

Run the application:

```powershell
streamlit run app.py
```

If the configuration is correct, Human In The Loop will be able to connect to Gemini and generate TypeScript code from task descriptions.

```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

### 6. Run the application

```powershell
streamlit run app.py
```

The application will be available at:

```text
http://localhost:8501
```
