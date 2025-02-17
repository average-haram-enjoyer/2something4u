from files.helpers.wrappers import *
from files.helpers.get import *

from files.__main__ import app, cache
from files.classes.submission import Submission

defaulttimefilter = environ.get("DEFAULT_TIME_FILTER", "all").strip()

@app.get("/post/")
def slash_post():
	return redirect("/")

@app.get("/notifications")
@auth_required
def notifications(v):
	try: page = int(request.values.get('page', 1))
	except: page = 1
	messages = request.values.get('messages', False)
	modmail = request.values.get('modmail', False)
	posts = request.values.get('posts', False)
	if modmail and v.admin_level == 6:
		comments = g.db.query(Comment).filter(Comment.sentto==0).order_by(Comment.created_utc.desc()).offset(25*(page-1)).limit(26).all()
		next_exists = (len(comments) > 25)
		comments = comments[:25]
	elif messages:
		comments = g.db.query(Comment).filter(or_(Comment.author_id==v.id, Comment.sentto==v.id), Comment.parent_submission == None).order_by(Comment.created_utc.desc(), not_(Comment.child_comments.any())).offset(25*(page-1)).limit(26).all()
		next_exists = (len(comments) > 25)
		comments = comments[:25]
	elif posts:
		notifications = v.notifications.join(Notification.comment).filter(Comment.author_id == AUTOJANNY_ACCOUNT).order_by(Notification.id.desc()).offset(25 * (page - 1)).limit(26).all()

		comments = []

		for index, x in enumerate(notifications):
			c = x.comment
			if x.read and index > 26: break
			elif not x.read:
				c.unread = True
				x.read = True
				g.db.add(x)
			comments.append(c)

		g.db.commit()

		next_exists = (len(comments) > 25)
		listing = comments[:25]
	else:

		notifications = v.notifications.join(Notification.comment).filter(
			Comment.is_banned == False,
			Comment.deleted_utc == 0,
			Comment.author_id != AUTOJANNY_ACCOUNT,
		).order_by(Notification.id.desc()).offset(25 * (page - 1)).limit(26).all()

		next_exists = (len(notifications) > 25)
		notifications = notifications[:25]
		cids = [x.comment_id for x in notifications]
		comments = get_comments(cids, v=v, load_parent=True)

		i = 0
		for x in notifications:
			try:
				if not x.read:
					comments[i].unread = True
					x.read = True
					g.db.add(x)
			except: continue
			i += 1

		g.db.commit()

	if not posts:
		listing = []
		for c in comments:
			c._is_blocked = False
			c._is_blocking = False
			if c.parent_submission and c.parent_comment and c.parent_comment.author_id == v.id:
				c.replies = []
				while c.parent_comment and c.parent_comment.author_id == v.id:
					parent = c.parent_comment
					if c not in parent.replies2:
						parent.replies2 = parent.replies2 + [c]
						parent.replies = parent.replies2
					c = parent
				if c not in listing:
					listing.append(c)
					c.replies = c.replies2
			elif c.parent_submission:
				c.replies = []
				if c not in listing:
					listing.append(c)
			else:
				if c.parent_comment:
					while c.level > 1:
						c = c.parent_comment

				if c not in listing:
					listing.append(c)


	return render_template("notifications.html",
						   v=v,
						   notifications=listing,
						   next_exists=next_exists,
						   page=page,
						   standalone=True,
						   render_replies=True,
						   is_notification_page=True)



@cache.memoize(timeout=86400)
def frontlist(v=None, sort="hot", page=1, t="all", ids_only=True, filter_words='', **kwargs):

	posts = g.db.query(Submission).options(lazyload('*'))

	if t != 'all':
		cutoff = 0
		now = int(time.time())
		if t == 'hour':
			cutoff = now - 3600
		elif t == 'day':
			cutoff = now - 86400
		elif t == 'week':
			cutoff = now - 604800
		elif t == 'month':
			cutoff = now - 2592000
		elif t == 'year':
			cutoff = now - 31536000
		posts = posts.filter(Submission.created_utc >= cutoff)

	posts = posts.filter_by(is_banned=False,stickied=False,private=False,deleted_utc = 0)

	if v:
		posts = posts.filter(or_(Submission.processing == False, Submission.author_id == v.id))
	else:
		posts = posts.filter_by(processing=False)

	if v and v.admin_level == 0:
		blocking = [x[0] for x in g.db.query(
			UserBlock.target_id).filter_by(
			user_id=v.id).all()]
		blocked = [x[0] for x in g.db.query(
			UserBlock.user_id).filter_by(
			target_id=v.id).all()]
		posts = posts.filter(
			Submission.author_id.notin_(blocking),
			Submission.author_id.notin_(blocked)
		)

	if not (v and v.changelogsub):
		posts=posts.join(Submission.submission_aux)
		posts=posts.filter(not_(SubmissionAux.title.ilike(f'[changelog]%')))

	if v and filter_words:
		for word in filter_words:
			posts=posts.filter(not_(SubmissionAux.title.ilike(f'%{word}%')))

	gt = kwargs.get("gt")
	lt = kwargs.get("lt")

	if gt:
		posts = posts.filter(Submission.created_utc > gt)

	if lt:
		posts = posts.filter(Submission.created_utc < lt)

	if not (v and v.shadowbanned):
		posts = posts.join(Submission.author).filter(User.shadowbanned == False)

	if sort == "hot":
		posts = sorted(posts.all(), key=lambda x: x.hotscore, reverse=True)
	elif sort == "new":
		posts = posts.order_by(Submission.created_utc.desc()).all()
	elif sort == "old":
		posts = posts.order_by(Submission.created_utc.asc()).all()
	elif sort == "controversial":
		posts = sorted(posts.all(), key=lambda x: x.score_disputed, reverse=True)
	elif sort == "top":
		posts = sorted(posts.all(), key=lambda x: x.score, reverse=True)
	elif sort == "bottom":
		posts = sorted(posts.all(), key=lambda x: x.score)
	elif sort == "comments":
		posts = posts.order_by(Submission.comment_count.desc()).all()
	elif sort == "random":
		posts = posts.all()
		posts = random.sample(posts, k=len(posts))
	else:
		abort(400)

	firstrange = 25 * (page - 1)
	secondrange = firstrange+100
	posts = posts[firstrange:secondrange]

	# if random.random() < 0.004:
	# 	for post in posts:
	# 		if post.author and post.author.shadowbanned:
	# 			rand = random.randint(5,20)
	# 			if post.score > rand: continue
	# 			rand = random.randint(500,1400)
	# 			vote = Vote(user_id=rand,
	# 				vote_type=random.choice([-1, 1, 1, 1, 1]),
	# 				submission_id=post.id)
	# 			g.db.add(vote)
	# 			try: g.db.flush()
	# 			except: g.db.rollback()
	# 			post.upvotes = g.db.query(Vote).options(lazyload('*')).filter_by(submission_id=post.id, vote_type=1).count()
	# 			post.downvotes = g.db.query(Vote).options(lazyload('*')).filter_by(submission_id=post.id, vote_type=-1).count()
	# 			post.views = post.views + random.randint(7,10)
	# 			g.db.add(post)

	next_exists = (len(posts) > 25)

	posts = posts[:25]

	if page == 1: posts = g.db.query(Submission).options(lazyload('*')).filter_by(stickied=True).all() + posts

	if ids_only: posts = [x.id for x in posts]

	return posts, next_exists

@app.get("/")
@app.get("/logged_out")
@auth_desired
def front_all(v):

	if not v and request.path == "/" and not request.headers.get("Authorization"): return redirect("/logged_out")

	if v and "logged_out" in request.full_path: v = None

	try: page = int(request.values.get("page") or 1)
	except: abort(400)

	# prevent invalid paging
	page = max(page, 1)

	if v:
		defaultsorting = v.defaultsorting
		defaulttime = v.defaulttime
	else:
		defaultsorting = "hot"
		defaulttime = defaulttimefilter

	sort=request.values.get("sort", defaultsorting)
	t=request.values.get('t', defaulttime)

	ids, next_exists = frontlist(sort=sort,
					page=page,
					t=t,
					v=v,
					gt=int(request.values.get("utc_greater_than", 0)),
					lt=int(request.values.get("utc_less_than", 0)),
					filter_words=v.filter_words if v else [],
					)

	posts = get_posts(ids, v=v)

	if v and v.hidevotedon: posts = [x for x in posts if not hasattr(x, 'voted') or not x.voted]

	if request.headers.get("Authorization"): return {"data": [x.json for x in posts], "next_exists": next_exists}
	else: return render_template("home.html", v=v, listing=posts, next_exists=next_exists, sort=sort, t=t, page=page)


@cache.memoize(timeout=86400)
def changeloglist(v=None, sort="new", page=1 ,t="all", **kwargs):

	posts = g.db.query(Submission).options(lazyload('*')).options(lazyload('*')).filter_by(is_banned=False, private=False,).filter(Submission.deleted_utc == 0)

	if v and v.admin_level == 0:
		blocking = [x[0] for x in g.db.query(
			UserBlock.target_id).filter_by(
			user_id=v.id).all()]
		blocked = [x[0] for x in g.db.query(
			UserBlock.user_id).filter_by(
			target_id=v.id).all()]
		posts = posts.filter(
			Submission.author_id.notin_(blocking),
			Submission.author_id.notin_(blocked)
		)

	posts=posts.join(Submission.submission_aux).join(Submission.author)
	posts=posts.filter(SubmissionAux.title.ilike(f'_changelog%', User.admin_level == 6))

	if t != 'all':
		cutoff = 0
		now = int(time.time())
		if t == 'hour':
			cutoff = now - 3600
		elif t == 'day':
			cutoff = now - 86400
		elif t == 'week':
			cutoff = now - 604800
		elif t == 'month':
			cutoff = now - 2592000
		elif t == 'year':
			cutoff = now - 31536000
		posts = posts.filter(Submission.created_utc >= cutoff)

	gt = kwargs.get("gt")
	lt = kwargs.get("lt")

	if gt:
		posts = posts.filter(Submission.created_utc > gt)

	if lt:
		posts = posts.filter(Submission.created_utc < lt)

	if sort == "hot":
		posts = sorted(posts.all(), key=lambda x: x.hotscore, reverse=True)
	elif sort == "new":
		posts = posts.order_by(Submission.created_utc.desc()).all()
	elif sort == "old":
		posts = posts.order_by(Submission.created_utc.asc()).all()
	elif sort == "controversial":
		posts = sorted(posts.all(), key=lambda x: x.score_disputed, reverse=True)
	elif sort == "top":
		posts = sorted(posts.all(), key=lambda x: x.score, reverse=True)
	elif sort == "bottom":
		posts = sorted(posts.all(), key=lambda x: x.score)
	elif sort == "comments":
		posts = posts.order_by(Submission.comment_count.desc()).all()
	elif sort == "random":
		posts = posts.all()
		posts = random.sample(posts, k=len(posts))
	else:
		abort(400)

	firstrange = 25 * (page - 1)
	secondrange = firstrange+26
	posts = posts[firstrange:secondrange]

	posts = [x.id for x in posts]
	return posts

@app.get("/changelog")
@auth_desired
def changelog(v):


	page = int(request.values.get("page") or 1)
	page = max(page, 1)

	sort=request.values.get("sort", "new")
	t=request.values.get('t', "all")

	ids = changeloglist(sort=sort,
					page=page,
					t=t,
					v=v,
					gt=int(request.values.get("utc_greater_than", 0)),
					lt=int(request.values.get("utc_less_than", 0)),
					)

	# check existence of next page
	next_exists = (len(ids) > 25)
	ids = ids[:25]

	# check if ids exist
	posts = get_posts(ids, v=v)

	if request.headers.get("Authorization"): return {"data": [x.json for x in posts], "next_exists": next_exists}
	else: return render_template("changelog.html", v=v, listing=posts, next_exists=next_exists, sort=sort, t=t, page=page)


@app.get("/random")
@auth_desired
def random_post(v):

	x = g.db.query(Submission).options(lazyload('*')).filter(Submission.deleted_utc == 0, Submission.is_banned == False)
	total = x.count()
	n = random.randint(1, total - 2)

	post = x.offset(n).limit(1).first()
	return redirect(f"/post/{post.id}")

@cache.memoize(timeout=86400)
def comment_idlist(page=1, v=None, nsfw=False, sort="new", t="all", **kwargs):

	posts = g.db.query(Submission).options(lazyload('*'))
	cc_idlist = [x[0] for x in g.db.query(Submission.id).options(lazyload('*')).filter(Submission.club == True).all()]

	posts = posts.subquery()

	comments = g.db.query(Comment).options(lazyload('*')).options(lazyload('*')).filter(Comment.parent_submission.notin_(cc_idlist))

	if v and v.admin_level <= 3:
		blocking = [x[0] for x in g.db.query(
			UserBlock.target_id).filter_by(
			user_id=v.id).all()]
		blocked = [x[0] for x in g.db.query(
			UserBlock.user_id).filter_by(
			target_id=v.id).all()]

		comments = comments.filter(
			Comment.author_id.notin_(blocking),
			Comment.author_id.notin_(blocked)
		)

	if not v or not v.admin_level >= 3:
		comments = comments.filter_by(is_banned=False).filter(Comment.deleted_utc == 0)

	comments = comments.join(posts, Comment.parent_submission == posts.c.id)

	now = int(time.time())
	if t == 'hour':
		cutoff = now - 3600
	elif t == 'day':
		cutoff = now - 86400
	elif t == 'week':
		cutoff = now - 604800
	elif t == 'month':
		cutoff = now - 2592000
	elif t == 'year':
		cutoff = now - 31536000
	else:
		cutoff = 0
	comments = comments.filter(Comment.created_utc >= cutoff)

	if sort == "new":
		comments = comments.order_by(Comment.created_utc.desc()).all()
	elif sort == "old":
		comments = comments.order_by(Comment.created_utc.asc()).all()
	elif sort == "controversial":
		comments = sorted(comments.all(), key=lambda x: x.score_disputed, reverse=True)
	elif sort == "top":
		comments = sorted(comments.all(), key=lambda x: x.score, reverse=True)
	elif sort == "bottom":
		comments = sorted(comments.all(), key=lambda x: x.score)

	firstrange = 25 * (page - 1)
	secondrange = firstrange+26
	comments = comments[firstrange:secondrange]

	return [x.id for x in comments]

@app.get("/comments")
@auth_desired
def all_comments(v):


	page = int(request.values.get("page", 1))

	sort=request.values.get("sort", "new")
	t=request.values.get("t", defaulttimefilter)

	idlist = comment_idlist(v=v,
							page=page,
							sort=sort,
							t=t,
							)

	comments = get_comments(idlist, v=v)

	next_exists = len(idlist) > 25

	idlist = idlist[:25]

	if request.headers.get("Authorization"): return {"data": [x.json for x in comments]}
	else: return render_template("home_comments.html", v=v, sort=sort, t=t, page=page, comments=comments, standalone=True, next_exists=next_exists)
