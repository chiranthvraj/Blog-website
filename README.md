# Little Stories

Little Stories is a beginner-friendly blogging website built with Flask, MongoDB, HTML, CSS, and Bootstrap. Visitors can read stories; registered users can publish posts, manage their own writing, and comment using straightforward web forms.

## What works

- Register with a name, email, and password. Email addresses are unique and passwords are stored as secure hashes.
- Log in and log out using a protected Flask session.
- Read story cards and full post pages.
- Publish, edit, and delete your own posts.
- View your posts on the **My posts** page.
- Add comments to stories and delete your own comments.
- Use JSON endpoints for the main account, post, and comment operations.
- See helpful messages when a request is invalid or MongoDB is unavailable.

Six sample stories appear when the database has no posts yet. They use Chiranth Vraj P, Bhuvan, Manoj, Sanketh, Prabhudev, and Nethra as example authors. Their `example.com` email addresses are display-only examples—not accounts and not passwords. Register with your own email to publish.

## Requirements

- Python 3.10 or newer
- MongoDB Community Server running locally, or a MongoDB Atlas connection string
- A browser and an internet connection for the Bootstrap stylesheet and Google Fonts

## Run in VS Code (Windows)

In VS Code, open the **`blogcreationwebsite` folder itself** using **File → Open Folder**. The parent internship folder contains a different `app.py`, so selecting or running that file starts another project.

**Quickest option:** open this folder in File Explorer and double-click `run_blog.bat`. It creates a project-local `.venv` and installs the dependencies if needed, opens the correct browser address, and keeps the server output visible in its window.

You can also open VS Code's terminal with **Terminal → New Terminal** and run `app.py` directly:

```powershell
python app.py
```

If `python` is not the right environment, use the existing environment To create the project's own Python environment, run these once in the VS Code terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Then start the website from the **project folder**:

```powershell
.\.venv\Scripts\python.exe app.py
```

**Use VS Code's F5 / Run and Debug button:** choose **Little Stories: Run Flask app** from the Run and Debug dropdown. The project includes settings for the project-local `.venv`.

If VS Code already remembered a different Python interpreter, use **Ctrl+Shift+P → Python: Select Interpreter**, then select `blogcreationwebsite\.venv\Scripts\python.exe`.

**Important:** do not open `templates\base.html` or `templates\index.html` directly, and do not use **Go Live** / Live Server. Those files contain Jinja templates that only Flask can render; direct opening shows `{% ... %}` and `{{ ... }}` as plain text. Run `app.py` and open the Flask address `http://127.0.0.1:5000` instead. Port `5500` is the Live Server address, not this Flask site. Keep the Python terminal open while using the site; press **Ctrl+C** there to stop it. If port 5000 is already in use, stop the other Flask server in its terminal first.

Open <http://127.0.0.1:5000>. Click **Create your free account**, register with your name and email, then use **Write a post** in the navigation or **Create a new post** on the page. Your published stories appear on the home page and in **My posts**.

The default local database settings are:

- MongoDB: `mongodb://127.0.0.1:27017`
- Database: `little_stories`

To use MongoDB Atlas or another database, set the environment variables in the same PowerShell terminal before starting Flask:

```powershell
$env:MONGO_URI = "your MongoDB connection string"
$env:MONGO_DATABASE = "little_stories"
$env:SECRET_KEY = "replace-this-with-a-long-random-secret"
..\.venv\Scripts\python.exe app.py
```

Use your own URI and secret; do not publish them or commit them to GitHub. The built-in development secret is only for local practice. For a deployed site, always set a private random `SECRET_KEY` and use HTTPS.

## API overview

The API accepts and returns JSON. For requests that change data, first load an HTML page and send its `csrf-token` meta value in the `X-CSRF-Token` request header. The browser login session is stored in a secure, HTTP-only session cookie.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/register` | Create an account (`name`, `email`, `password`) |
| POST | `/api/login` | Log in (`email`, `password`) |
| POST | `/api/logout` | Log out |
| GET | `/api/posts` | List posts |
| POST | `/api/posts` | Create a post (`title`, `content`) |
| GET | `/api/posts/<id>` | Read a post |
| PUT | `/api/posts/<id>` | Edit your own post |
| DELETE | `/api/posts/<id>` | Delete your own post and its comments |
| GET | `/api/posts/<id>/comments` | List comments |
| POST | `/api/posts/<id>/comments` | Add a comment (`text`) |
| DELETE | `/api/comments/<id>` | Delete your own comment |

## Run the tests

Tests use a separate, uniquely named MongoDB database and delete only that test database when they finish. MongoDB must be running.

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Project layout

```text
blogcreationwebsite/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── create_post.html
│   ├── edit_post.html
│   ├── post.html
│   ├── my_posts.html
│   └── error.html
├── static/
│   └── css/
│       └── style.css
└── tests/
    └── test_app.py
```
