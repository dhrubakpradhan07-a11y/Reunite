"""Integration tests: run `python -m unittest discover -s tests -v` after pip install."""
import io
import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from app import create_app


class ReuniteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ['DATA_DIR'] = self.temp.name
        self.app = create_app({'TESTING': True})
        self.client = self.app.test_client()
        self.csrf = self.client.get('/api/config').json['csrf']
        self.headers = {'X-CSRF-Token': self.csrf}

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop('DATA_DIR', None)

    def create_report(self, item_type='lost', title='Blue notebook', category='Books', location='Main library', photo=None):
        data = {
            'type': item_type, 'title': title,
            'description': 'This item has a bright blue cover and a small sticker.',
            'category': category, 'location': location,
            'item_date': '2026-01-01', 'reporter_name': 'Alex Test',
            'reporter_email': 'alex@example.com', 'color': 'Blue',
        }
        if photo is not None:
            data['photo'] = photo
        return self.client.post('/api/items', data=data, headers=self.headers)

    def test_create_and_privacy(self):
        r = self.create_report()
        self.assertEqual(r.status_code, 201, r.json)
        self.assertEqual(r.json['item']['reporter_first_name'], 'Alex')
        self.assertNotIn('reporter_email', r.json['item'])
        feed = self.client.get('/api/items?q=notebook').json
        self.assertEqual(feed['total'], 1)
        self.assertNotIn('reporter_email', feed['items'][0])

    def test_csrf_required(self):
        r = self.client.post('/api/items', data={'title': 'No token'})
        self.assertEqual(r.status_code, 403)

    def test_message_and_reunion(self):
        created = self.create_report().json
        item_id = created['item']['id']
        token = created['manage_url'].split('/')[-1]
        r = self.client.post(f'/api/items/{item_id}/inquiries', json={
            'sender_name': 'Taylor', 'sender_contact': 'taylor@example.com',
            'message': 'I may have found your notebook outside the entrance.'
        }, headers=self.headers)
        self.assertEqual(r.status_code, 201, r.json)
        own = self.client.get(f'/api/manage/{token}').json
        self.assertEqual(len(own['inquiries']), 1)
        self.assertEqual(own['item']['reporter_email'], 'alex@example.com')
        marked = self.client.patch(f'/api/manage/{token}', json={'status': 'reunited'}, headers=self.headers)
        self.assertEqual(marked.json['status'], 'reunited')
        self.assertEqual(self.client.get('/api/stats').json['reunited'], 1)
        self.assertEqual(self.client.delete(f'/api/manage/{token}', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/api/stats').json['total'], 0)

    def test_upload_converts_image(self):
        img = Image.new('RGB', (120, 110), (28, 104, 76))
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)
        r = self.create_report(photo=(buf, 'my_photo.png'))
        self.assertEqual(r.status_code, 201, r.json)
        self.assertTrue(r.json['item']['photo_url'].endswith('.webp'))
        with self.app.app_context():
            url = r.json['item']['photo_url']
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_smart_matching(self):
        lost = self.create_report('lost', 'Blue notebook', 'Books', 'Main library').json['item']
        found = self.create_report('found', 'Found blue notebook', 'Books', 'Main library').json['item']
        result = self.client.get(f'/api/items/{lost["id"]}/matches').json['matches']
        self.assertEqual(result[0]['id'], found['id'])
        self.assertGreaterEqual(result[0]['match_score'], 38)


if __name__ == '__main__':
    unittest.main()
