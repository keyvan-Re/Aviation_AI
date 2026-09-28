# ✈️ Aviation AI Assistant

A chat assistant built with **Streamlit** that answers aviation and aircraft maintenance questions using your own PDF manuals. It uses **RAG** (Retrieval-Augmented Generation): it searches your documents first, then writes an answer and shows the sources it used.

> ⚠️ **Safety notice:** Answers are made by AI. A certified mechanic must always check any maintenance action before it is done.

---

## Features

- 🔐 **User accounts** – register and log in. Passwords are hashed with `bcrypt`.
- 💬 **Multiple chats** – create, rename, archive, and delete chats. Archived chats are read-only.
- 📚 **Answers from your PDFs** – finds the best matching parts of your manuals (FAISS vector search) and answers from them.
- 📑 **Sources shown** – every answer can show the document name and page number it used.
- 🖼️ **Image input** – attach a photo, part, or schematic (`png`, `jpg`, `jpeg`). The assistant describes it and uses it in the search.
- 🎙️ **Voice input** – record a message and it is turned into text with Whisper.
- 🧠 **Chat memory** – follow-up questions are rewritten so they make sense on their own before searching.
- ✏️ **Edit last question** – change your last question and get a new answer.
- 📋 **Copy button** – copy any message with one click.
- 🚫 **Honest answers** – if the answer is not in the documents, the assistant says so.

---

## Project Structure

```
.
├── app.py              # Main Streamlit app (chat, sidebar, RAG logic)
├── auth.py             # Login, register, and chat/message database functions
├── create_db.py        # Builds the vector database from your PDFs
├── docs/               # Put your PDF files here (you create this folder)
├── my_vector_db/       # FAISS index (created by create_db.py)
└── database/
    └── users.db        # SQLite database (created automatically)
```

---

## Requirements

- Python 3.10 or newer
- An OpenAI-compatible API key and base URL

Install the packages:

```bash
pip install streamlit bcrypt openai faiss-cpu pypdf \
    langchain-community langchain-openai langchain-core \
    langchain-text-splitters langchain-classic
```

---

## Setup

### 1. Clone the project

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2. Set your environment variables

The app needs these two variables:

| Variable         | Description                                      |
| ---------------- | ------------------------------------------------ |
| `OPENAI_API_KEY` | Your API key                                     |
| `BASE_URL`       | API address, for example `https://api.openai.com/v1` |

**Linux / macOS**

```bash
export OPENAI_API_KEY="your-key-here"
export BASE_URL="https://api.openai.com/v1"
```

**Windows (PowerShell)**

```powershell
$env:OPENAI_API_KEY="your-key-here"
$env:BASE_URL="https://api.openai.com/v1"
```

> 🔒 **Never write your API key inside the code or upload it to GitHub.**
> Make sure `create_db.py` also reads the key from the environment:
>
> ```python
> import os
> embeddings = OpenAIEmbeddings(
>     openai_api_key=os.environ["OPENAI_API_KEY"],
>     openai_api_base=os.environ["BASE_URL"],
> )
> ```

### 3. Add your documents

Create a folder named `docs` and copy your PDF manuals into it.

### 4. Build the vector database

```bash
python create_db.py
```

This reads all PDFs in `docs/`, splits them into small parts (1000 characters, 100 overlap), and saves the index in `my_vector_db/`.

Run this step again whenever you add or change PDFs.

### 5. Start the app

```bash
streamlit run app.py
```

Open the link shown in the terminal (usually `http://localhost:8501`).

---

## How It Works

1. **You ask a question** (text, voice, or with an image).
2. If there is an image, the model writes a short description of it.
3. If the chat has history, your question is rewritten as a full, standalone question.
4. The **top 3 matching parts** are found in the FAISS database.
5. The model (`gpt-4o`) answers using **only** that context and gives sources like `[Manual.pdf, Page 8]`.
6. The answer and sources are saved in the SQLite database for that chat.

---

## Configuration

You can change these settings in the code:

| Setting            | Where            | Default   |
| ------------------ | ---------------- | --------- |
| Chat model         | `app.py`         | `gpt-4o`  |
| Speech-to-text     | `app.py`         | `whisper-1` |
| Parts returned     | `app.py` (`k`)   | `3`       |
| Chunk size         | `create_db.py`   | `1000`    |
| Chunk overlap      | `create_db.py`   | `100`     |
| Password min length | `auth.py`       | `6`       |

---

## Database

The app uses SQLite (`database/users.db`) with three tables:

- `users` – username and hashed password
- `chats` – chat title, owner, and archive status
- `messages` – chat messages and their sources

---

## Security Notes

- Passwords are stored as `bcrypt` hashes, never as plain text.
- Keep your API key in environment variables only.
- `FAISS.load_local(..., allow_dangerous_deserialization=True)` is used. Only load a vector database that **you** created.
- Add these to your `.gitignore`:

  ```
  database/
  my_vector_db/
  docs/
  .env
  ```

---

## Limitations

- Answers are only as good as the documents you provide.
- Not a replacement for a certified aircraft mechanic or official procedures.
- The assistant is set to answer in English.

---

## License

Add your license here (for example, MIT).
