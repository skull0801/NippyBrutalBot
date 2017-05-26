from __future__ import print_function
import praw
import os
import time
import re
import sys
import sqlite3
import configparser
import content_matching
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
    valid_categories = ['hot', 'new', 'top', 'controversial', 'rising']
    default_category = 'hot'

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
        self.setup_matchers()

    def setup_matchers(self):
        brutal_nippy = "Brutal{0}Savage{0}Rekt{0}|Nippy{0}Kind{0}Langur{0}".format("[.,\s]+")
        url = "gfycat.com/(BrutalSavageRekt|NippyKindLangur)"
        simple_matcher = content_matching.ContentMatcher(patterns=[(url, None, 0),
                                                                   (brutal_nippy, "[.,\s]", 20)])
        chain_matcher1 = content_matching.ChainContentMatcher(patterns=[(x + "[.,\s]*", "[.,\s]", 15) for x in ["Rekt", "Savage", "Brutal"]])
        chain_matcher2 = content_matching.ChainContentMatcher(patterns=[(x + "[.,\s]*", "[.,\s]", 15) for x in ["Langur", "Kind", "Nippy"]])

        submission_matcher = content_matching.ContentMatcher(patterns=[(brutal_nippy, "[.,\s]", 0),
                                                                       (brutal_nippy, "[.,\s]", 0),
                                                                       (url, None, 0)])

        self.comment_matchers = [simple_matcher, chain_matcher1, chain_matcher2]
        self.submission_matchers = [submission_matcher]


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

    #section_limits should be arguments with the key being the category (e.g. hot, new, top) and value the limit of posts, e.g hot=5, new=10
    def get_submissions(self, sub_names=None, **section_limits):
        if sub_names is None:
            sub_names = self.subreddits_to_search
        subs = self.reddit.subreddit(sub_names)
        result = []

        if not section_limits:
            print("Getting default values in get_submissions")
            section_limits[NippyBot.default_category] = self.posts_limit

        for section, limit in section_limits.items():
            if section in NippyBot.valid_categories:
                func = getattr(subs, section)
                result = result + [submission for submission in func(limit=limit) if self.is_submission_fresh(submission)]
            else:
                print("WARNING: unrecognized category in 'get_submissions': {}".format(section))

        return result

    def parse_comment(self, comment):
        content = content_matching.CommentContent(comment)
        for matcher in self.comment_matchers:
            content.reset()
            result = matcher.match(content)
            if result:
                return result

    def parse_submission(self, submission):
        content = content_matching.SubmissionContent(submission)
        for matcher in self.submission_matchers:
            content.reset()
            result = matcher.match(content)
            if result:
                return result
