"""
API Server - REST API for LeadMakingMachine
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3


class APIServer:
    def __init__(self, settings):
        self.settings = settings
        self.app = Flask(__name__)
        CORS(self.app)
        self.db_path = settings.db_path_absolute
        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes"""

        @self.app.route('/api/health', methods=['GET'])
        def health():
            return jsonify({'status': 'ok', 'service': 'LeadMakingMachine'})

        @self.app.route('/api/stats', methods=['GET'])
        def stats():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}
            cursor.execute("SELECT COUNT(*) FROM leads")
            stats['total_leads'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'emailed'")
            stats['emailed'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'responded'")
            stats['responded'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'sent'")
            stats['emails_sent'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM campaigns")
            stats['campaigns'] = cursor.fetchone()[0]

            conn.close()
            return jsonify(stats)

        @self.app.route('/api/leads', methods=['GET'])
        def get_leads():
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)
            status = request.args.get('status')

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    "SELECT * FROM leads WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (status, limit, offset)
                )
            else:
                cursor.execute(
                    "SELECT * FROM leads ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )

            leads = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify(leads)

        @self.app.route('/api/leads/<int:lead_id>', methods=['GET'])
        def get_lead(lead_id):
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return jsonify(dict(row))
            return jsonify({'error': 'Lead not found'}), 404

        @self.app.route('/api/leads', methods=['POST'])
        def create_lead():
            data = request.json

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO leads (company, email, phone, website, industry, location, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('company', ''),
                data.get('email', ''),
                data.get('phone', ''),
                data.get('website', ''),
                data.get('industry', ''),
                data.get('location', ''),
                data.get('status', 'new')
            ))

            lead_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return jsonify({'id': lead_id, 'status': 'created'}), 201

        @self.app.route('/api/leads/<int:lead_id>', methods=['PUT'])
        def update_lead(lead_id):
            data = request.json

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE leads SET
                    company = COALESCE(?, company),
                    email = COALESCE(?, email),
                    phone = COALESCE(?, phone),
                    website = COALESCE(?, website),
                    industry = COALESCE(?, industry),
                    location = COALESCE(?, location),
                    status = COALESCE(?, status),
                    notes = COALESCE(?, notes),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data.get('company'),
                data.get('email'),
                data.get('phone'),
                data.get('website'),
                data.get('industry'),
                data.get('location'),
                data.get('status'),
                data.get('notes'),
                lead_id
            ))

            conn.commit()
            affected = cursor.rowcount
            conn.close()

            if affected:
                return jsonify({'status': 'updated'})
            return jsonify({'error': 'Lead not found'}), 404

        @self.app.route('/api/campaigns', methods=['GET'])
        def get_campaigns():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM campaigns ORDER BY id DESC")
            campaigns = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify(campaigns)

        @self.app.route('/api/campaigns', methods=['POST'])
        def create_campaign():
            data = request.json

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO campaigns (name, subject, template, status)
                VALUES (?, ?, ?, ?)
            """, (
                data.get('name', ''),
                data.get('subject', ''),
                data.get('template', ''),
                data.get('status', 'draft')
            ))

            campaign_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return jsonify({'id': campaign_id, 'status': 'created'}), 201

        @self.app.route('/api/emails', methods=['GET'])
        def get_emails():
            lead_id = request.args.get('lead_id', type=int)

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if lead_id:
                cursor.execute(
                    "SELECT * FROM emails WHERE lead_id = ? ORDER BY sent_at DESC",
                    (lead_id,)
                )
            else:
                cursor.execute("SELECT * FROM emails ORDER BY sent_at DESC LIMIT 100")

            emails = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify(emails)

        @self.app.route('/api/responses', methods=['GET'])
        def get_responses():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT r.*, l.company, l.email as lead_email
                FROM responses r
                JOIN leads l ON r.lead_id = l.id
                ORDER BY r.received_at DESC
            """)

            responses = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return jsonify(responses)

    def run(self, host='0.0.0.0', port=5000):
        """Run the Flask server"""
        self.app.run(host=host, port=port, debug=False)
