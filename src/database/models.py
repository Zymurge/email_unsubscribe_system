"""
Database models for the email subscription manager.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, 
    Boolean, create_engine, Index
)
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Account(Base):
    """Email account information."""
    __tablename__ = 'accounts'

    id = Column(Integer, primary_key=True)
    email_address = Column(String(255), unique=True, nullable=False)
    provider = Column(String(50), nullable=False)  # gmail, comcast, outlook, etc.
    imap_server = Column(String(255))
    imap_port = Column(Integer, default=993)
    use_ssl = Column(Boolean, default=True)
    last_scan = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="account", cascade="all, delete-orphan")
    email_messages = relationship("EmailMessage", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account(email='{self.email_address}', provider='{self.provider}')>"


class EmailMessage(Base):
    """Individual email messages that have been scanned."""
    __tablename__ = 'email_messages'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    message_id = Column(String(255), nullable=False)  # Email Message-ID header
    uid = Column(Integer)  # IMAP UID
    folder = Column(String(255), default='INBOX')
    sender_email = Column(String(255), nullable=False)
    sender_name = Column(String(255))
    subject = Column(Text)
    date_sent = Column(DateTime)
    date_received = Column(DateTime, default=func.now())
    has_unsubscribe_header = Column(Boolean, default=False)
    has_unsubscribe_link = Column(Boolean, default=False)
    processed_for_subscriptions = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="email_messages")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_account_message_id', 'account_id', 'message_id'),
        Index('idx_sender_email', 'sender_email'),
        Index('idx_date_sent', 'date_sent'),
        Index('idx_unsubscribe_flags', 'has_unsubscribe_header', 'has_unsubscribe_link'),
    )

    def __repr__(self):
        return f"<EmailMessage(sender='{self.sender_email}', subject='{self.subject[:50]}...')>"


class Subscription(Base):
    """Discovered email subscriptions."""
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    sender_email = Column(String(255), nullable=False)
    sender_name = Column(String(255))
    sender_domain = Column(String(255))  # Extracted from sender_email
    subject_pattern = Column(Text)
    unsubscribe_link = Column(Text)
    unsubscribe_method = Column(String(50))  # http_get, http_post, email_reply, one_click
    list_id = Column(String(255))  # From List-ID header
    frequency = Column(String(50))  # daily, weekly, monthly, irregular
    category = Column(String(100))  # marketing, newsletter, notification, transactional
    confidence_score = Column(Integer, default=0)  # 0-100, how confident we are this is a subscription
    discovered_at = Column(DateTime, default=func.now())
    last_seen = Column(DateTime, default=func.now())
    email_count = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    account = relationship("Account", back_populates="subscriptions")
    unsubscribe_attempts = relationship("UnsubscribeAttempt", back_populates="subscription", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_account_sender', 'account_id', 'sender_email'),
        Index('idx_sender_domain', 'sender_domain'),
        Index('idx_category', 'category'),
        Index('idx_active_subs', 'is_active', 'confidence_score'),
    )

    def __repr__(self):
        return f"<Subscription(sender='{self.sender_email}', category='{self.category}')>"


class UnsubscribeAttempt(Base):
    """Track unsubscribe attempts and their results."""
    __tablename__ = 'unsubscribe_attempts'

    id = Column(Integer, primary_key=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    attempted_at = Column(DateTime, default=func.now())
    method_used = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)  # success, failed, pending, skipped
    response_code = Column(Integer)
    response_headers = Column(Text)
    error_message = Column(Text)
    notes = Column(Text)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="unsubscribe_attempts")
    
    def __repr__(self):
        return f"<UnsubscribeAttempt(subscription_id={self.subscription_id}, status='{self.status}')>"


def create_database_engine(database_url: str = "sqlite:///email_subscriptions.db"):
    """Create and return a database engine."""
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return engine


def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def get_session_maker(engine):
    """Get a session maker for the database."""
    return sessionmaker(bind=engine)