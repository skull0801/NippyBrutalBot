import praw
import os
import time
import re
from datetime import datetime

bot_name = "NippyBrutalBot".lower()
dry_run = False

regex = "gfycat.com/(BrutalSavageRekt|NippyKindLangur)"
terms = ["gfycat.com/BrutalSavageRekt", "gfycat.com/NippyKindLangur"]
terms = [term.lower() for term in terms]
replies = ["gfycat.com/NippyKindLangur", "gfycat.com/BrutalSavageRekt"]

subreddits_to_search = "Dota2"
posts_limit = 25
post_age_limit = 24 * 60 * 60 # in seconds

#used when scraping old posts
#TODO: use SQL to store manipulated comments
filename_replied_comments = "comments_replied_to.txt"

# getting id for posts replied to
if not os.path.isfile(filename_replied_comments):
    comments_replied_to = []
else:
    with open(filename_replied_comments, "r") as f:
        # read all posts ids splitting by new lines and remove nil values
        comments_replied_to = list(filter(None, f.read().split("\n")))

reddit = praw.Reddit('bot1')
subreddits = reddit.subreddit(subreddits_to_search)

for submission in subreddits.hot(limit=posts_limit):
    submission_date = datetime.fromtimestamp(submission.created_utc)
    limit_date = datetime.fromtimestamp(time.time() - post_age_limit)
    #checking if post is too old
    if (submission_date > limit_date):
        all_comments = submission.comments
        all_comments.replace_more(limit=None, threshold=0) #get all comments from thread
        flat_comments = all_comments.list() # comments in list instead of tree
        for comment in flat_comments:
            if str(comment.author).lower() != bot_name: #checking if comment not made by bot
                #TODO: check if comment already checked in a better way
                if comment.id not in comments_replied_to:
                    match = re.search(regex, comment.body, re.IGNORECASE)
                    if match:
                        index = terms.index(match[0].lower())
                        reply = "https://" + replies[index]
                        print("Replying to {0}'s comment with {1}. Original comment: {2}".format(comment.author, reply, comment.body))
                        if not dry_run:
                            comments_replied_to.append(comment.id)
                            comment.reply(reply)

with open(filename_replied_comments, "w") as f:
    for comment_id in comments_replied_to:
        f.write("{}\n".format(comment))

'''
try:
    for comment in subreddits.stream.comments():
        #checking if comment was not made by the bot
        if comment.author.name.lower() != bot_name:
            for index, term in terms_enumerator:
                if re.search(term, comment.body, re.IGNORECASE):
                    reply = "https://" + replies[index]
                    print("Replying to {0}'s comment with {1}. Original comment: {2}".format(comment.author, reply, comment.permalink()))
                    comment.reply(reply)
except KeyboardInterrupt:
    print("Exiting program")
'''
