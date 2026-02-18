from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from .models import Connection, Conversation, Message


# ---------- CONNECTION LOGIC ----------

def request_connection(db: Session, requester_id: str, target_id: str):
    if requester_id == target_id:
        raise ValueError("Cannot connect to self")

    existing = db.query(Connection).filter(
        or_(
            and_(
                Connection.requester_id == requester_id,
                Connection.target_id == target_id,
            ),
            and_(
                Connection.requester_id == target_id,
                Connection.target_id == requester_id,
            ),
        ),
        Connection.status.in_(["pending", "accepted"]),
    ).first()

    if existing:
        return existing

    conn = Connection(
        requester_id=requester_id,
        target_id=target_id,
        status="pending",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def accept_connection(db: Session, connection_id: int, accepter_id: str):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise ValueError("Connection not found")

    if accepter_id not in [conn.requester_id, conn.target_id]:
        raise ValueError("Not authorized")

    conn.status = "accepted"

    convo = Conversation(
        user_a=conn.requester_id,
        user_b=conn.target_id,
    )

    db.add(convo)
    db.commit()
    db.refresh(convo)

    return convo


def reject_connection(db: Session, connection_id: int, rejecter_id: str):
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise ValueError("Connection not found")

    if rejecter_id not in [conn.requester_id, conn.target_id]:
        raise ValueError("Not authorized")

    conn.status = "rejected"
    db.commit()
    return conn


# ---------- MESSAGING ----------

def send_message(db: Session, conversation_id: int, sender_id: str, body: str):
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise ValueError("Conversation not found")

    if sender_id not in [convo.user_a, convo.user_b]:
        raise ValueError("Not authorized")

    msg = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        body=body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_messages(db: Session, conversation_id: int):
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
