import re
import unittest
import uuid

from app import create_app


class BlogPlatformTests(unittest.TestCase):
    def setUp(self):
        self.database_name = "little_stories_test_" + uuid.uuid4().hex
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "MONGO_DATABASE": self.database_name,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.mongo_client.drop_database(self.database_name)
        self.app.mongo_client.close()

    def csrf_token(self, client=None, path="/register"):
        response = (client or self.client).get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'<meta name="csrf-token" content="([^"]+)"', response.data)
        self.assertIsNotNone(match, "The page should expose a CSRF token for forms.")
        return match.group(1).decode()

    def register(self, client=None, name="Test Writer", email=None):
        client = client or self.client
        email = email or "writer-" + uuid.uuid4().hex + "@example.test"
        response = client.post(
            "/register",
            data={
                "csrf_token": self.csrf_token(client),
                "name": name,
                "email": email,
                "password": "correct horse battery",
            },
        )
        self.assertEqual(response.status_code, 302)
        return email

    def test_home_seeds_readable_sample_stories_and_real_navigation(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        for author in ("Chiranth Vraj P", "Bhuvan", "Manoj", "Sanketh", "Prabhudev", "Nethra"):
            self.assertIn(author.encode(), response.data)
        self.assertIn(b"CREATIVITY", response.data)
        self.assertIn(b"LEARNING", response.data)
        self.assertIn(b"Create your free account", response.data)
        self.assertIn(b"sample only", response.data)
        post = self.app.mongo_db.posts.find_one({"is_demo": True})
        self.assertIsNotNone(post)
        self.assertEqual(self.client.get("/posts/not-an-id").status_code, 404)

    def test_registration_duplicate_password_login_and_logout(self):
        email = self.register()
        user = self.app.mongo_db.users.find_one({"email": email})
        self.assertNotIn("password", user)
        self.assertNotEqual(user["password_hash"], "correct horse battery")

        token = self.csrf_token(path="/")
        duplicate = self.client.post(
            "/api/register",
            json={"name": "Another Writer", "email": email, "password": "correct horse battery"},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(duplicate.status_code, 409)

        logout_token = self.csrf_token(path="/")
        logout = self.client.post("/api/logout", headers={"X-CSRF-Token": logout_token})
        self.assertEqual(logout.status_code, 200)

        login_token = self.csrf_token(path="/login")
        wrong_password = self.client.post(
            "/api/login",
            json={"email": email, "password": "not-the-password"},
            headers={"X-CSRF-Token": login_token},
        )
        self.assertEqual(wrong_password.status_code, 401)

        login_token = self.csrf_token(path="/login")
        login = self.client.post(
            "/api/login",
            json={"email": email, "password": "correct horse battery"},
            headers={"X-CSRF-Token": login_token},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["user"]["email"], email)

    def test_post_crud_ownership_and_comment_permissions(self):
        self.register()
        writer_token = self.csrf_token(path="/")
        created = self.client.post(
            "/api/posts",
            json={"title": "A real story", "content": "A useful first paragraph."},
            headers={"X-CSRF-Token": writer_token},
        )
        self.assertEqual(created.status_code, 201)
        post = created.get_json()["post"]
        post_id = post["id"]
        self.assertEqual(self.client.get("/api/posts/" + post_id).status_code, 200)
        posts = self.client.get("/api/posts").get_json()["posts"]
        self.assertEqual(sum(not post["is_demo"] for post in posts), 1)

        editor = self.app.test_client()
        self.register(editor, name="Different Writer")
        editor_token = self.csrf_token(editor, "/")
        forbidden_edit = editor.put(
            "/api/posts/" + post_id,
            json={"title": "Changed by another user", "content": "No permission."},
            headers={"X-CSRF-Token": editor_token},
        )
        self.assertEqual(forbidden_edit.status_code, 403)
        forbidden_delete = editor.delete(
            "/api/posts/" + post_id,
            headers={"X-CSRF-Token": editor_token},
        )
        self.assertEqual(forbidden_delete.status_code, 403)

        comment = editor.post(
            "/api/posts/" + post_id + "/comments",
            json={"text": "A thoughtful comment."},
            headers={"X-CSRF-Token": editor_token},
        )
        self.assertEqual(comment.status_code, 201)
        comment_id = comment.get_json()["comment"]["id"]
        self.assertEqual(len(self.client.get("/api/posts/" + post_id + "/comments").get_json()["comments"]), 1)
        self.assertEqual(
            self.client.delete(
                "/api/comments/" + comment_id,
                headers={"X-CSRF-Token": writer_token},
            ).status_code,
            403,
        )
        self.assertEqual(
            editor.delete(
                "/api/comments/" + comment_id,
                headers={"X-CSRF-Token": editor_token},
            ).status_code,
            200,
        )

        writer_token = self.csrf_token(path="/")
        edited = self.client.put(
            "/api/posts/" + post_id,
            json={"title": "Edited story", "content": "The updated story."},
            headers={"X-CSRF-Token": writer_token},
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.get_json()["post"]["title"], "Edited story")
        comment_before_delete = editor.post(
            "/api/posts/" + post_id + "/comments",
            json={"text": "This comment should be removed with the post."},
            headers={"X-CSRF-Token": editor_token},
        )
        self.assertEqual(comment_before_delete.status_code, 201)
        deleted = self.client.delete(
            "/api/posts/" + post_id,
            headers={"X-CSRF-Token": writer_token},
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/posts/" + post_id).status_code, 404)
        self.assertEqual(self.app.mongo_db.comments.count_documents({}), 0)

    def test_html_create_edit_dashboard_and_delete_flow(self):
        self.register()
        new_post = self.client.post(
            "/posts/new",
            data={
                "csrf_token": self.csrf_token(path="/posts/new"),
                "title": "HTML post",
                "content": "Published using the website form.",
            },
        )
        self.assertEqual(new_post.status_code, 302)
        detail_url = new_post.headers["Location"]
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Edit post", detail.data)

        dashboard = self.client.get("/my-posts")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"HTML post", dashboard.data)
        post_id = detail_url.rsplit("/", 1)[-1]
        comment = self.client.post(
            "/posts/{}/comments".format(post_id),
            data={
                "csrf_token": self.csrf_token(path=detail_url),
                "text": "A comment from the website.",
            },
        )
        self.assertEqual(comment.status_code, 302)
        stored_comment = self.app.mongo_db.comments.find_one()
        self.assertIsNotNone(stored_comment)
        self.assertIn(b"A comment from the website.", self.client.get(detail_url).data)
        delete_comment = self.client.post(
            "/comments/{}/delete".format(stored_comment["_id"]),
            data={"csrf_token": self.csrf_token(path=detail_url)},
        )
        self.assertEqual(delete_comment.status_code, 302)
        self.assertEqual(self.app.mongo_db.comments.count_documents({}), 0)
        edit = self.client.post(
            "/posts/{}/edit".format(post_id),
            data={
                "csrf_token": self.csrf_token(path="/posts/{}/edit".format(post_id)),
                "title": "Updated HTML post",
                "content": "Updated through the website form.",
            },
        )
        self.assertEqual(edit.status_code, 302)
        self.assertIn(b"Updated HTML post", self.client.get(detail_url).data)

        delete = self.client.post(
            "/posts/{}/delete".format(post_id),
            data={"csrf_token": self.csrf_token(path=detail_url)},
        )
        self.assertEqual(delete.status_code, 302)
        self.assertEqual(self.client.get(detail_url).status_code, 404)

    def test_private_api_requires_login_and_csrf(self):
        unauthenticated = self.client.post("/api/posts", json={"title": "No", "content": "No"})
        self.assertEqual(unauthenticated.status_code, 401)
        self.register()
        missing_token = self.client.post("/api/posts", json={"title": "No", "content": "No"})
        self.assertEqual(missing_token.status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/posts",
                json={"title": "", "content": ""},
                headers={"X-CSRF-Token": self.csrf_token(path="/")},
            ).status_code,
            400,
        )


if __name__ == "__main__":
    unittest.main()
