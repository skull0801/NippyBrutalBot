from __future__ import print_function
import winsound
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

stdout = sys.stdout
stderr = sys.stderr

def log(*args, **kwargs):
    print(*args, file=stdout, **kwargs)

def log_error(*args, **kwargs):
    print(time.strftime("%a %Y-%m-%d %H:%M:%S -", time.localtime()), *args, file=stderr, **kwargs)

def match_regex(content, pattern, sanitizer=None, max_size=0, ignore_case=True):
    def sanitize(string, sanitizer=None):
        if sanitizer:
            return re.sub(sanitizer, '', string)
        else:
            return string

    flags = re.IGNORECASE if ignore_case else 0
    if max_size > 0 and len(content) > max_size:
        return None
    match = re.search(pattern, content, flags)
    if match:
        return sanitize(match[0], sanitizer=sanitizer)
    else:
        return None

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
                 sleep_delay=1800,
                 verbose=False):
        # setting variables
        self.bot_name = bot_name.lower()
        self.dry_run = dry_run
        self.subreddits_to_search = subreddits_to_search
        self.posts_limit = posts_limit
        self.db_file = db_file
        self.post_age_limit = post_age_limit
        self.reset_database = reset_database
        self.sleep_delay = sleep_delay
        self.verbose = verbose
        # connecting to reddit
        self.reddit = praw.Reddit(praw_bot_name)

        self.comments_checked, self.comments_matched, self.comments_replied, self.comments_saved = 0, 0, 0, 0

        self.reply_terms = {"gfycat.com/BrutalSavageRekt": 0,
                            "gfycat.com/NippyKindLangur": 1,
                            "NippyKindLangur": 1,
                            "BrutalSavageRekt": 0,
                            "Rekt": 0,
                            "Langur": 1}
        nip = "gfycat.com/NippyKindLangur"
        bru = "gfycat.com/BrutalSavageRekt"
        self.reply_regexes = {"gfycat.com/BrutalSavageRekt": nip,
                              "gfycat.com/NippyKindLangur": bru,
                              "NippyKindLangur": bru,
                              "BrutalSavageRekt": nip,
                              "Rekt": nip,
                              "Langur": bru}
        self.reply_terms = dict((k.lower(), v) for k, v in self.reply_terms.items())
        self.reply_regexes = dict((k.lower(), v) for k, v in self.reply_regexes.items())
        self.replies = ["https://gfycat.com/NippyKindLangur", "https://gfycat.com/BrutalSavageRekt"]

        self.setup_db(self.db_file, self.reset_database)
        self.setup_matchers()

    def setup_matchers(self):
        brutal_nippy = "Brutal{0}Savage{0}Rekt{0}|Nippy{0}Kind{0}Langur{0}".format("[.,\s]*")
        url = "gfycat.com/(BrutalSavageRekt|NippyKindLangur)"

        simple_matcher = content_matching.ContentMatcher(patterns=[(url, None, 0), (brutal_nippy, "[.,\s]", 100)])
        chain_matcher1 = content_matching.ChainContentMatcher(patterns=[(x + "[.,\s]*", "[.,\s]", 15) for x in ["Rekt", "Savage", "Brutal"]])
        chain_matcher2 = content_matching.ChainContentMatcher(patterns=[(x + "[.,\s]*", "[.,\s]", 15) for x in ["Langur", "Kind", "Nippy"]])

        self.comment_matchers = [simple_matcher, chain_matcher1, chain_matcher2]
        self.submission_matchers = [(brutal_nippy, "[.,\s]", 0), (brutal_nippy, "[.,\s]", 0), (url, None, 0)]


    def setup_db(self, filename, reset_database=False):
        # connecting to database
        self.connection = sqlite3.connect(filename)
        self.c = self.connection.cursor()

        # create tables if they don't exist
        with open(self.sql_creation) as f:
            self.c.executescript(f.read())
            self.connection.commit()

        if reset_database:
            self.reset_db()

    def reset_db(self):
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
        result = set()

        if not section_limits:
            section_limits[NippyBot.default_category] = self.posts_limit

        for section, limit in section_limits.items():
            if section in NippyBot.valid_categories:
                func = getattr(subs, section)
                result = result.union({submission for submission in func(limit=limit) if self.is_submission_fresh(submission)})

        return list(result)

    def get_comments_from_sub(self, sub_names, limit):
        return list(self.reddit.subreddit(sub_names).comments(limit=limit))

    def parse_comment(self, comment):
        content = content_matching.CommentContent(comment)
        for matcher in self.comment_matchers:
            content.reset()
            result = matcher.match(content)
            if result:
                return result


    def parse_submission(self, submission):
        if submission.is_self:
            text_post_matcher = self.submission_matchers[0]
            result = match_regex(submission.selftext, text_post_matcher[0], sanitizer=text_post_matcher[1], max_size=text_post_matcher[2])
            if result:
                return result
        title_matcher = self.submission_matchers[1]
        result1 = match_regex(submission.title, title_matcher[0], sanitizer=title_matcher[1], max_size=title_matcher[2])
        result2 = None

        if not submission.is_self:
            url_matcher = self.submission_matchers[2]
            result2 = match_regex(submission.url, url_matcher[0], sanitizer=url_matcher[1], max_size=url_matcher[2])

        if result1 and result2: #if post has a match on title and links to it, don't reply
            return None
        if result1:
            return result1
        return result2

    def is_comment_logged(self, comment):
        self.c.execute(select_comment_with_id, [comment.id])
        if self.c.fetchone() is None:
            self.c.execute(select_to_reply_with_id, [comment.id])
            return self.c.fetchone() is not None
        else:
            return True

    def is_submission_logged(self, submission):
        self.c.execute(select_comment_with_id, [submission.name])
        return self.c.fetchone() is not None

    def log_comment(self, comment, valid=True):
        if not self.dry_run:
            self.c.execute(insert_comment, [comment.id, comment.permalink(), time.time(), 1 if valid else 0])

    def log_submission(self, submission):
        if not self.dry_run:
            self.c.execute(insert_comment, [submission.name, submission.permalink, time.time(), 1])

    def is_comment_reply_to_bot(self, comment):
        if comment.is_root:
            return False
        parent = comment.parent()
        return parent.author and parent.author.name.lower() == self.bot_name

    def validate_comments(self, comments_to_reply, matches):
        invalid = set()
        for comment in comments_to_reply:
            has_parent = not comment.is_root
            if self.is_comment_reply_to_bot(comment) or (has_parent and self.is_comment_logged(comment.parent())):
                invalid.add(comment)
            elif has_parent:
                parent = comment.parent()
                if not parent.body:
                    continue
                match = self.parse_comment(parent)
                if match:
                    match = match[0][0]
                    regex = self.regex_for_reply_for_match(match)
                    possible = re.search(regex, comment.body, re.IGNORECASE)
                    if possible:
                        invalid.add(comment)
                        invalid.add(parent)

        return list(comments_to_reply - invalid), list(invalid)

    def reply_for_match(self, match):
        if match is None:
            return None
        return self.replies[self.reply_terms[match.lower()]]

    def regex_for_reply_for_match(self, match):
        if match is None:
            return None
        return self.reply_regexes[match.lower()]

    def reply_later(self, comment, reply):
        self.c.execute(insert_to_reply, [comment.id, reply])
        if self.verbose:
            log("Saving comment [[{}]] to reply later, reply: \'{}\'".format(comment.id, reply))

    def reply_to_old_comments(self):
        self.c.execute(select_to_reply)
        comments = self.c.fetchall()
        #TODO: validate if old_comments should still be replied to
        replied = set()
        if comments and self.verbose:
            log("Replying to old comments. (There are {} comments to reply to).".format(len(comments)))
        for comment_info in comments:
            comment = self.reddit.comment(comment_info[0])
            try:
                self.reply_to_comment(comment, comment_info[1])
                self.c.execute(delete_to_reply, [comment.id])
                self.log_comment(comment, True)
                replied.add(comment)
            except praw.exceptions.PRAWException as e:
                return replied
        self.connection.commit()
        return replied

    def reply_to_comment(self, comment, reply=None):
        if reply is None:
            match = self.parse_comment(comment)
            if match is None:
                return None
            match = match[0][0]
            reply = self.reply_for_match(match)
            if reply is None:
                return
        if self.verbose:
            log("Replying to {0}'s comment with {1}. Original comment permalink: https://reddit.com{2}".format(comment.author.name, reply, comment.permalink()))
        if not self.dry_run:
            comment.reply(reply)

    def reply_to_submission(self, submission, reply=None):
        if reply is None:
            match = self.parse_submission(submission)
            if match is None:
                return None
            match = match[0][0]
            reply = self.reply_for_match(match)
            if reply is None:
                return
        if self.verbose:
            log("Replying to {0}'s post with {1}. Original post permalink: https://reddit.com{2}".format(submission.author.name, reply, submission.url))
        if not self.dry_run:
            submission.reply(reply)

    def delete_comments(self, limit=100, from_subreddits=None, below_threshold=None):
        if from_subreddits:
            from_subreddits = [sub.lower() for sub in from_subreddits]
        me = self.reddit.user.me()
        comments = list(me.comments.new(limit=limit))
        deleted = set()
        for comment in comments:
            sub_matches = not bool(from_subreddits) or comment.subreddit.display_name.lower() in from_subreddits
            if sub_matches:
                threshold_met = below_threshold is None or comment.score < below_threshold
                if threshold_met:
                    comment.delete()
                    deleted.add(comment)
        return deleted


    def get_comments(self, submission):
        all_comments = submission.comments
        all_comments.replace_more(limit=None, threshold=0)
        flat_comments = all_comments.list()
        return flat_comments

    def get_comments_to_reply(self, comments):
        matches = dict()
        to_reply = set()
        comments_checked, comments_matched = 0, 0
        for comment in comments:
            #TODO handle better comments that were deleted
            if comment.author is None:
                continue
            self.comments_checked += 1
            comments_checked += 1

            #comment not made or replied already by bot
            if comment.author.name.lower() != self.bot_name and not self.is_comment_logged(comment):
                match = self.parse_comment(comment)
                if match is not None:
                    matches[comment.id] = match
                    to_reply.add(comment)
                    self.comments_matched += 1
                    comments_matched += 1

        return matches, to_reply, comments_checked, comments_matched

    def parse_comments(self, comments, commit=False):
        comments_checked, comments_matched, comments_replied, comments_saved = 0, 0, 0, 0

        matches, to_reply, checked, matched = self.get_comments_to_reply(comments)
        comments_checked += checked
        comments_matched += matched

        # remove comments already replied to or that are replies to something the bot would've replied
        valid_comments, invalid_comments = self.validate_comments(comments_to_reply=to_reply, matches=matches)

        for comment in invalid_comments:
            if not self.is_comment_logged(comment):
                self.log_comment(comment, False)
            if self.verbose:
                log("Would've replied to {0}'s comment but it either was already replied to or is a reply. Original comment permalink: https://reddit.com{1}".format(comment.author, comment.permalink()))

        for comment in valid_comments:
            match = matches[comment.id]
            reply = self.reply_for_match(match[0][0])
            try:
                self.reply_to_comment(comment, reply)
                self.log_comment(comment)
                for m in match[1:]:
                    #logging parent comments to the one being answered
                    self.log_comment(m[1], valid=False)
                self.comments_replied += 1
                comments_replied += 1
            except praw.exceptions.PRAWException as e:
                if self.verbose:
                    log_error("Error when trying to reply to comment, saving for later. Comment permalink = https://reddit.com{}. [{}]".format(comment.permalink(), e))
                self.reply_later(comment, reply)
                self.comments_saved += 1
                comments_saved += 1

        if commit:
            self.connection.commit()

        return (comments_checked, comments_matched, comments_replied, comments_saved)

    def parse_submissions(self, submissions, check_comments=True):
        comments_checked, comments_matched, comments_replied, comments_saved, submissions_replied = 0, 0, 0, 0, 0
        for submission in submissions:
            if not self.is_submission_logged(submission):
                submission_match = self.parse_submission(submission)
                if submission_match:
                    self.reply_to_submission(submission, self.reply_for_match(submission_match))
                    self.log_submission(submission)
                    submissions_replied += 1

            if not check_comments:
                continue

            comments = self.get_comments(submission)

            result = self.parse_comments(comments, commit=False)

            comments_checked += result[0]
            comments_matched += result[1]
            comments_replied += result[2]
            comments_saved += result[3]

        self.connection.commit()
        return (comments_checked, comments_matched, comments_replied, comments_saved, submissions_replied)

    def finish(self):
        self.connection.close()

if __name__ == '__main__':
    winsound.Beep(700, 90)
    configs_file = 'nippy_bot.cfg'
    c = configparser.ConfigParser()
    c.read(configs_file)

    bot_name = c['variables']['BotName'].lower()
    dry_run = eval(c['variables']['DryRun'])
    subreddits_to_search = c['variables']['Subs']
    posts_limit = int(c['variables']['MaxPosts'])
    db_file = c['variables']['DataBaseFileName']
    post_age_limit = eval(c['variables']['MaxPostAge'])
    reset_database = eval(c['variables']['ResetDB'])
    sleep_delay = eval(c['variables']['SleepDelay'])
    score_threshold = int(c['variables']['DeleteBelowScore'])
    out = c['variables']['LogFile']
    err = c['variables']['ErrorLogFile']

    if out != 'None':
        stdout = open(out, 'a')

    if err != 'None':
        stderr = open(err, 'a')

    log(time.strftime("Start time: %a %Y-%m-%d %H:%M:%S", time.localtime()))

    bot = NippyBot(bot_name=bot_name,
                   praw_bot_name='bot1',
                   subreddits_to_search=subreddits_to_search,
                   posts_limit=posts_limit,
                   dry_run=dry_run,
                   post_age_limit=post_age_limit,
                   db_file=db_file,
                   reset_database=reset_database,
                   sleep_delay=sleep_delay,
                   verbose=True)

    limit = 10
    log("Deleting comments below threshold. (limit={}, threshold={})".format(limit, score_threshold))
    deleted = bot.delete_comments(limit=limit, from_subreddits=None, below_threshold=score_threshold)
    for comment in deleted:
        log("Deleted comment {} with score of {}.".format(comment.body, comment.score))

    log("Searching for new comments to reply on /r/{}.".format(subreddits_to_search))
    submissions = bot.get_submissions(sub_names=subreddits_to_search, hot=50, rising=15, controversial=15)
    result = bot.parse_submissions(submissions)
    log("All operations done. {} submissions checked. {} comments checked. {} comments matched. {} comments invalidated. {} comments replied to. {} comments saved for later. {} submissions replied to.".format(len(submissions), result[0], result[1], result[2], result[2], result[3], result[4]))
    log(time.strftime("End time: %a %Y-%m-%d %H:%M:%S", time.localtime()))
    log("---------------------------------")
    bot.finish()

    stdout.close()
    stderr.close()
    winsound.Beep(250, 150)
