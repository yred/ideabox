from django.test import TestCase
from django.test import Client

class BoxesTest(TestCase):
    def test_session_based_box(self):
        c = Client()
        resp = c.get('/')
        self.assertEqual(resp.status_code, 200)
        resp = c.post('/', {'name': 'box_name'}, follow=True)
        self.assertEqual(resp.redirect_chain[0][1], 302)
        self.assertEqual(resp.status_code, 200)
        
