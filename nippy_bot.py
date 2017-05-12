from __future__ import print_function
import praw
import os
import time
import re
import sys
import sqlite3
import configparser
from datetime import datetime

configs_file = 'nippy_bot.cfg'
c = configparser.ConfigParser()
c.read(configs_file)

bot_name = c['variables']['BotName'].lower()
dry_run = eval(c['variables']['DryRun'])
subreddits_to_search = c['variables']['Subs']
posts_limit = eval(c['variables']['MaxPosts'])
post_age_limit = eval(c['variables']['MaxPostAge'])
reset_database = eval(c['variables']['ResetDB'])
sleep_delay = eval(c['variables']['SleepDelay'])

# for printing errors
def eprint(*args, **kwargs):
    print(time.strftime("%a %Y-%m-%d %H:%M:%S -", time.localtime()), *args, file=sys.stderr, **kwargs)

def get_reply(match):
    index = terms.index(match.lower())
    reply = "https://" + replies[index]
    return reply

def reply_to_comment(comment, reply):
    print("Replying to {0}'s comment with {1}. Original comment permalink: reddit.com{2}".format(comment.author, reply, comment.permalink()))
    if not dry_run:
        comment.reply(reply)

def get_match(string):
    match = re.search(regex, string, re.IGNORECASE)
    if match:
        return match[0]
    else:
        match = re.search(regex2, string, re.IGNORECASE)
        if match:
            match = re.sub('[.,\s]', '', match[0])
        return match

def was_comment_checked(comment):
    c.execute(select_comment_with_id, [comment.id])
    if c.fetchone() == None:
        c.execute(select_to_reply_with_id, [comment.id])
        return c.fetchone() != None
    else:
        return True

def register_comment(comment, valid):
    c.execute(insert_comment, [comment.id, comment.permalink(), time.time(), 1 if valid else 0])
    connection.commit()

def save_comment_to_reply(comment, reply):
    print("Saving comment [[{}]] to reply later, reply: \'{}\'".format(comment.id, reply))
    c.execute(insert_to_reply, [comment.id, reply])
    connection.commit()

def is_top_level_comment(comment):
    return comment.link_id == comment.parent_id

def comment_matches(comment):
    if not is_top_level_comment(comment):
        if comment_matches(comment.parent()):
            return True
        else:
            if was_comment_replied(comment):
                return False
            else:
                return True
    elif was_comment_replied(comment):
        return False
    else:
        return True

# checks if comment has already been replied with a comment the bot would've given
def was_comment_replied(comment):
    #TODO implement
    return False

def is_not_reply(comment):
    #TODO: check if comment was made in reply to bot
    return True

def reply_to_old_comments(comments):
    #TODO: validate if old_comments should still be replied to
    for comment_info in comments:
        comment = reddit.comment(comment_info[0])
        try:
            reply_to_comment(comment, comment_info[1])
            c.execute(delete_to_reply, [comment.id])
            register_comment(comment, True)
        except praw.exceptions.PRAWException as e:
            print("Failed to reply to old comment, will try again later")
            return

print(time.strftime("Start time: %a %Y-%m-%d %H:%M:%S", time.localtime()))

#connecting to database
connection = sqlite3.connect('database.db')
c = connection.cursor()

## used only when creating
# with open('create_db.sql') as f:
#     c.executescript(f.read())
#     connection.commit()
if reset_database:
    with open('clean_db.sql') as f:
        c.executescript(f.read())
        connection.commit()

#sql commands
select_comment_with_id = 'SELECT ID FROM comments WHERE ID = ?'
insert_comment = 'INSERT INTO comments (ID, PERMALINK, DATE_ADDED, VALID) VALUES (?, ?, ?, ?)'
insert_to_reply = 'INSERT INTO to_reply (ID, RESPONSE) VALUES (?, ?)'
select_to_reply = 'SELECT ID, RESPONSE FROM to_reply'
select_to_reply_with_id = 'SELECT ID FROM to_reply WHERE ID = ?'
delete_to_reply = 'DELETE FROM to_reply WHERE ID = ?'

# regex to find match in comment and reply
regex = "gfycat.com/(BrutalSavageRekt|NippyKindLangur)"
regex2 = "(Brutal{}Savage{}Rekt{}|Nippy{}Kind{}Langur{})".replace('{}', '[.,\s]*')
terms = ["gfycat.com/BrutalSavageRekt", "gfycat.com/NippyKindLangur", "NippyKindLangur", "BrutalSavageRekt"]
# #test terms
# regex = "word|nice"
# terms = ["word", "nice"]
terms = [term.lower() for term in terms]
replies = ["gfycat.com/NippyKindLangur", "gfycat.com/BrutalSavageRekt", "gfycat.com/BrutalSavageRekt", "gfycat.com/NippyKindLangur"]

reddit = praw.Reddit('bot1')
subreddits = reddit.subreddit(subreddits_to_search)

c.execute(select_to_reply)
comments_to_reply = c.fetchall()
if comments_to_reply:
    print("Replying to old comments first. (There are {} comments to reply to)".format(len(comments_to_reply)))
    reply_to_old_comments(comments_to_reply)
else:
    print("No old comments to reply to.")

print("Searching for new comments to reply.")

comments_checked, comments_matched, comments_replied, comments_saved = 0, 0, 0, 0
for submission in subreddits.hot(limit=posts_limit):
    submission_date = datetime.fromtimestamp(submission.created_utc)
    limit_date = datetime.fromtimestamp(time.time() - post_age_limit)
    #checking if post is too old
    if (submission_date > limit_date):
        all_comments = submission.comments
        all_comments.replace_more(limit=None, threshold=0) #get all comments from thread
        flat_comments = all_comments.list() # comments in list instead of tree
        #sweeping through comments and getting possible matches
        to_reply = set()
        matches = {}
        for comment in flat_comments:
            comments_checked += 1
            if str(comment.author).lower() != bot_name: #checking if comment not made by bot
                if not was_comment_checked(comment): #if comment was not already replied (or will be replied to)
                    match = get_match(comment.body)
                    if match:
                        matches[comment.id] = match
                        to_reply.add(comment)
                        comments_matched += 1

        to_reply_ids = {comment.id for comment in to_reply}
        to_remove = set()
        #removing invalid comments
        for comment in to_reply:
            if is_top_level_comment(comment):
                continue
            if was_comment_checked(comment.parent()) or comment.parent().id in to_reply_ids:
                to_remove.add(comment)
                to_remove.add(comment.parent())

        for comment in to_remove:
            if not was_comment_checked(comment):
                register_comment(comment, False)
            #print("Would've replied to {0}'s comment but it either was already replied to or is a reply. Original comment permalink: reddit.com{1}".format(comment.author, comment.permalink()))

        to_reply = list(to_reply - to_remove)
        for comment in to_reply:
            match = matches[comment.id]
            reply = get_reply(match)
            try:
                reply_to_comment(comment, reply)
                register_comment(comment, True)
                comments_replied += 1
            except praw.exceptions.PRAWException as e:
                eprint("Error when trying to reply to comment, saving for later. Comment permalink = https://reddit.com{}. [{}]".format(comment.permalink(), e))
                save_comment_to_reply(comment, reply)
                comments_saved += 1



print("All operations done. {} comments checked. {} comments matched. {} comments invalidated. {} comments replied to. {} comments saved for later.".format(comments_checked, comments_matched, comments_matched - comments_replied, comments_replied, comments_saved))
print(time.strftime("End time: %a %Y-%m-%d %H:%M:%S", time.localtime()))
print("---------------------------------")

# closing db connection
connection.close()

# with open(filename_replied_comments, "w") as f:
#     for comment_id in comments_replied_to:
#         f.write("{}\n".format(comment))


# try:
#     for comment in subreddits.stream.comments():
#         #checking if comment was not made by the bot
#         if comment.author.name.lower() != bot_name:
#             for index, term in terms_enumerator:
#                 if re.search(term, comment.body, re.IGNORECASE):
#                     reply = "https://" + replies[index]
#                     print("Replying to {0}'s comment with {1}. Original comment: {2}".format(comment.author, reply, comment.permalink()))
#                     comment.reply(reply)
# except KeyboardInterrupt:
#     print("Exiting program")
