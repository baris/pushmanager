import sqlalchemy as SA

import core.db as db
from core.mail import MailQueue
from core.requesthandler import RequestHandler
import core.util

class DiscardRequestServlet(RequestHandler):

    def post(self):
        if not self.current_user:
            return self.send_error(403)
        self.requestid = core.util.get_int_arg(self.request, 'id')
        update_query = db.push_requests.update().where(SA.and_(
            db.push_requests.c.id == self.requestid,
            db.push_requests.c.user == self.current_user,
            db.push_requests.c.state.in_(['requested', 'delayed']),
        )).values({
            'state': 'discarded',
        })
        select_query = db.push_requests.select().where(
            db.push_requests.c.id == self.requestid,
        )
        db.execute_transaction_cb([update_query, select_query], self.on_db_complete)
    # allow both GET and POST
    get = post

    def on_db_complete(self, success, db_results):
        self.check_db_results(success, db_results)

        _, req = db_results
        req = req.first()
        if req['state'] != 'discarded':
            # We didn't actually discard the record, for whatever reason
            return self.redirect("/requests?user=%s" % self.current_user)

        msg = (
            """
            <p>
                Your request has been discarded:
            </p>
            <p>
                <strong>%(user)s - %(title)s</strong><br />
                <em>%(repo)s/%(branch)s</em>
            </p>
            <p>
                Regards,<br />
                PushManager
            </p>"""
            ) % core.util.EscapedDict({
                'pushmaster': self.current_user,
                'user': req['user'],
                'title': req['title'],
                'repo': req['repo'],
                'branch': req['branch'],
            })
        subject = "[push] %s - %s" % (req['user'], req['title'])
        MailQueue.enqueue_user_email([req['user']], msg, subject)

        self.redirect("/requests?user=%s" % self.current_user)

