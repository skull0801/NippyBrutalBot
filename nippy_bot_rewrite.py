from __future__ import print_function
import praw
import os
import time
import re
import sys
import sqlite3
import configparser
from datetime import datetime

#sql commands
select_comment_with_id = 'SELECT ID FROM comments WHERE ID = ?'
insert_comment = 'INSERT INTO comments (ID, PERMALINK, DATE_ADDED, VALID) VALUES (?, ?, ?, ?)'
insert_to_reply = 'INSERT INTO to_reply (ID, RESPONSE) VALUES (?, ?)'
select_to_reply = 'SELECT ID, RESPONSE FROM to_reply'
select_to_reply_with_id = 'SELECT ID FROM to_reply WHERE ID = ?'
delete_to_reply = 'DELETE FROM to_reply WHERE ID = ?'

class NippyBot:
    sql_creation = 'create_db.sql'
    sql_clean = 'clean_db.sql'

    def __init__(self, bot_name='NippyBrutalBot',
                 praw_bot_name='bot1',
                 subreddits_to_search='Dota2',
                 posts_limit=25,
                 dry_run=False,
                 post_age_limit=(24 * 60 * 60),
                 db_file='database.db',
                 reset_database=False,
                 sleep_delay=1800):
        # setting variables
        self.bot_name = bot_name
        self.dry_run = dry_run
        self.subreddits_to_search = subreddits_to_search
        self.posts_limit = posts_limit
        self.db_file = db_file
        self.post_age_limit = post_age_limit
        self.reset_database = reset_database
        self.sleep_delay = sleep_delay
        # connecting to reddit
        self.reddit = praw.Reddit(praw_bot_name)

        self.setup_db(self.db_file, self.reset_database)

    def setup_db(self, filename, reset_database=False):
        # connecting to database
        self.connection = sqlite3.connect(filename)
        self.c = self.connection.cursor()

        # create tables if they don't exist
        with open(self.sql_creation) as f:
            self.c.executescript(f.read())
            self.connection.commit()

        if reset_database:
            with open(self.sql_clean) as f:
                self.c.executescript(f.read())
                self.connection.commit()

    def is_submission_fresh(self, submission):
        submission_date = datetime.fromtimestamp(submission.created_utc)
        limit_date = datetime.fromtimestamp(time.time() - self.post_age_limit)
        return submission_date > limit_date

    def get_submissions(self, sub_names=None, get_new=False):
        if sub_names is None:
            sub_names = self.subreddits_to_search
        subs = self.reddit.subreddit(sub_names)
        limit = self.posts_limit/2 if get_new else self.posts_limit

        result = [submission for submission in subs.hot(limit=limit) if self.is_submission_fresh(submission)]

        if get_new:
            if self.posts_limit%2==1:
                limit = limit + 1
            for submission in subs.new(limit=limit):
                if self.is_submission_fresh(submission):
                    result.append(submission)

        return result
