# Smart Face Recognition Attendance System

A face recognition-based attendance management system built using **OpenCV, YuNet, SFace, FastAPI, React, and SQLite**. The system automates student attendance through facial recognition and provides separate dashboards for teachers and students.

## Overview

Traditional attendance methods can be time-consuming and require manual intervention. This project aims to simplify the process through automated face recognition, real-time attendance tracking, and a web-based management dashboard.

The system uses YuNet for face detection and SFace for facial feature extraction and recognition. A FastAPI backend manages application logic and communicates with an SQLite database, while the React frontend provides an interactive dashboard.

## Key Features

- **Face Detection:** Detects faces using the YuNet deep learning model.
- **Face Recognition:** Identifies registered students using SFace facial embeddings.
- **Automated Attendance:** Records attendance when a registered student is successfully recognized.
- **Teacher Dashboard:** Provides attendance statistics, student management, and attendance records.
- **Student Dashboard:** Allows students to view their attendance history and attendance percentage.
- **Attendance Correction:** Students can raise attendance correction requests through a token-based workflow.
- **Notification System:** Teachers can review and approve or reject student correction requests.
- **Attendance Buffer:** Displays the pre-class attendance buffer period.
- **Database Management:** Uses SQLite to maintain student information and attendance records.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React.js, CSS |
| Backend | Python, FastAPI |
| Face Detection | OpenCV, YuNet |
| Face Recognition | OpenCV, SFace |
| Database | SQLite |
| Development Tools | VS Code, Git, GitHub |

## System Architecture

The application follows a client-server architecture:

1. **Face Recognition Layer:** Captures video through a webcam, detects faces, and generates facial embeddings.
2. **Backend Layer:** FastAPI processes requests, manages attendance operations, and communicates with the database.
3. **Database Layer:** SQLite stores student information, facial embeddings, and attendance records.
4. **Frontend Layer:** React displays dashboards and allows teachers and students to interact with the system.

## Project Structure

```text
smart-attendance/
│
├── frontend/             # React frontend
│
├── models/               # YuNet and SFace model files
│
├── api.py                # FastAPI backend
├── recognize_teacher.py  # Face recognition script
├── attendance.db         # Local SQLite database (not committed)
├── requirements.txt      # Python dependencies
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10 or later
- Node.js and npm
- Git
- Webcam
- YuNet and SFace ONNX model files

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/smart-face-recognition-attendance.git
cd smart-face-recognition-attendance
```

### 2. Set Up the Python Backend

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 3. Start the FastAPI Backend

```bash
python -m uvicorn api:app --reload
```

The backend will run at:

`http://127.0.0.1:8000`

FastAPI documentation:

`http://127.0.0.1:8000/docs`

### 4. Start the React Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend will run at:

`http://localhost:5173`

### 5. Run Face Recognition

From the main project directory, activate the virtual environment if necessary and run:

```bash
python recognize_teacher.py
```

Ensure that your webcam is connected and the required ONNX model files are available in the expected locations.

## Future Enhancements

- Integration with existing classroom CCTV cameras using RTSP video streams.
- Multi-classroom attendance monitoring.
- ESP32-based hardware integration.
- Improved recognition under different lighting conditions and camera angles.
- Enhanced security and biometric data protection.

## Privacy and Security

This project is developed for academic and demonstration purposes. Facial embeddings and attendance information are sensitive data. Any real-world deployment should include appropriate consent, access controls, secure storage, and compliance with applicable data protection requirements.

## Project Information

**Project:** Smart Face Recognition Attendance System

**Institution:** Vellore Institute of Technology (VIT), Vellore

**Domain:** Computer Vision | Web Development | Artificial Intelligence

**Status:** Academic Project – Working Prototype

---

*Developed as an academic project exploring the integration of computer vision and web technologies for automated attendance management.*
