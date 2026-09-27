from types import SimpleNamespace


class Message:
    def __init__(self, text="", message_id=1):
        self.text = text
        self.message_id = message_id
        self.sent = []
        self.replies = []
        self.markup = None
        self.record = None

    async def reply_text(self, text, **kwargs):
        self.sent.append({"text": text, **kwargs})
        reply = Message(text, self.message_id + len(self.sent))
        reply.markup = kwargs.get("reply_markup")
        reply.record = self.sent[-1]
        self.replies.append(reply)
        return reply

    async def edit_text(self, text, **kwargs):
        self.text = text
        self.markup = kwargs.get("reply_markup")
        if self.record is not None:
            self.record.update(text=text, **kwargs)
        return self


class Callback:
    def __init__(self, message, data):
        self.message = message
        self.data = data

    async def answer(self):
        pass


def update(message, data=None, user_id=101):
    return SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=303),
        callback_query=Callback(message, data) if data else None,
    )


def context():
    return SimpleNamespace(user_data={}, application=SimpleNamespace(bot_data={}))


def torrent(**overrides):
    info = {
        "hash": "a" * 40,
        "name": "Test download",
        "state": "downloading",
        "progress": 0.5,
        "amount_left": 512,
        "total_size": 1024,
        "eta": 60,
        "dlspeed": 128,
        "upspeed": 0,
    }
    return {**info, **overrides}
