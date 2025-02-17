from flask import *
from sqlalchemy import *
from sqlalchemy.orm import relationship, lazyload
from .submission import Submission
from .comment import Comment
from files.__main__ import Base
from files.helpers.lazy import lazy
import time

class OauthApp(Base):

	__tablename__ = "oauth_apps"

	id = Column(Integer, primary_key=True)
	client_id = Column(String(64))
	app_name = Column(String(50))
	redirect_uri = Column(String(4096))
	description = Column(String(256))
	author_id = Column(Integer, ForeignKey("users.id"))
	author = relationship("User", viewonly=True)

	def __repr__(self): return f"<OauthApp(id={self.id})>"


	@property
	@lazy
	def created_date(self):
		return time.strftime("%d %B %Y", time.gmtime(self.created_utc))

	@property
	@lazy
	def created_datetime(self):
		return str(time.strftime("%d/%B/%Y %H:%M:%S UTC", time.gmtime(self.created_utc)))

	@property
	@lazy
	def permalink(self): return f"/admin/app/{self.id}"

	@lazy
	def idlist(self, page=1, **kwargs):

		posts = g.db.query(Submission.id).options(lazyload('*')).options(lazyload('*')).filter_by(app_id=self.id)
		
		posts=posts.order_by(Submission.created_utc.desc())

		posts=posts.offset(100*(page-1)).limit(101)

		return [x[0] for x in posts.all()]

	@lazy
	def comments_idlist(self, page=1, **kwargs):

		posts = g.db.query(Comment.id).options(lazyload('*')).options(lazyload('*')).filter_by(app_id=self.id)
		
		posts=posts.order_by(Comment.created_utc.desc())

		posts=posts.offset(100*(page-1)).limit(101)

		return [x[0] for x in posts.all()]



class ClientAuth(Base):

	__tablename__ = "client_auths"

	id = Column(Integer, primary_key=True)
	oauth_client = Column(Integer, ForeignKey("oauth_apps.id"))
	access_token = Column(String(128))
	user_id = Column(Integer, ForeignKey("users.id"))
	user = relationship("User", lazy="joined", viewonly=True)
	application = relationship("OauthApp", lazy="joined", viewonly=True)

	@property
	@lazy
	def created_date(self):
		return time.strftime("%d %B %Y", time.gmtime(self.created_utc))

	@property
	@lazy
	def created_datetime(self):
		return str(time.strftime("%d/%B/%Y %H:%M:%S UTC", time.gmtime(self.created_utc)))