# 🧩 Recursive File Decompressor Web App

A web-based tool that automatically extracts multi-layer compressed files and returns the final decompressed result.

Built using **Python + Flask**, this project is designed to handle nested archives commonly found in **CTF challenges, forensics tasks, and real-world scenarios**.

---

## 🚀 Features

* 📦 Supports multiple archive formats:

  * `.zip`
  * `.tar`
  * `.gz`
  * `.bz2`
  * `.xz`

* 🔁 Recursive extraction
  Automatically decompresses files until no compressed layers remain.

* 🧠 Smart file detection
  Uses **magic bytes** instead of relying only on file extensions.

* 📁 Handles nested folders
  Works even if archives are buried inside directories.

* 🛡️ Security-aware design

  * Limits extraction depth
  * Prevents malicious file paths (Zip Slip)
  * File size restrictions

* 📄 Optional text preview
  Displays content if the final file is a `.txt`

---

## 🏗️ Project Structure

```
decompressor-webapp/
│
├── app.py                # Flask backend
├── decompressor.py      # Core extraction logic
├── requirements.txt
│
├── uploads/             # Uploaded files
├── extracted/           # Temporary extracted files
│
├── templates/
│   └── index.html       # Frontend UI
│
└── static/              # CSS / JS (optional)
```

---

## ⚙️ Installation

### 1. Clone the repository

```
git clone https://github.com/your-username/decompressor-webapp.git
cd decompressor-webapp
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Install system dependency (Linux) 

```
sudo apt install libmagic1
```

---

## ▶️ Running the App

Start the Flask server:

```
python app.py
```

Open your browser and go to:

```
http://127.0.0.1:5000
```

---

## 🧪 How to Use

1. Upload a compressed file (can be multi-layered)
2. Click **Decompress**
3. The server will:

   * Extract all layers
   * Detect the final file
4. Download the final decompressed file

---

## 🧠 Example

Input:

```
challenge.zip
   └── secret.tar
         └── data.gz
               └── flag.txt
```

Output:

```
flag.txt
```

---

## 🔐 Security Considerations

This project includes basic protections against:

* **Zip Bombs**
  Limits recursion depth to prevent infinite extraction.

* **Path Traversal (Zip Slip)**
  Ensures extracted files cannot escape the working directory.

* **Large File Uploads**
  Configurable file size limit.

---

## 📌 Configuration

Inside `app.py`:

```python
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB limit
MAX_DEPTH = 50
```

---

## 💡 Future Improvements

* Drag & drop file upload UI (still on development)
* Automatic flag detection (`flag{}` patterns)
* Multi-file batch upload
* Docker support

---

## 🧑‍💻 Tech Stack

* Python 3
* Flask
* python-magic

---

## 📜 License

This project is open-source and free to use.

---

## 🤝 Contribution

Feel free to fork this repo and improve it.
Pull requests are welcome!

---

## ⚡ Author

Built by Supro 🚀
