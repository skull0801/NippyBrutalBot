import praw
import os
import re

bot_name = "NippyBrutalBot".lower()

terms_to_match = ["gfycat.com/BrutalSavageRekt", "gfycat.com/NippyKindLangur"]
replies = ["gfycat.com/NippyKindLangur", "gfycat.com/BrutalSavageRekt"]
terms_enumerator = enumerate(terms_to_match)

subreddits_to_search = "Dota2"

#used when scraping old posts
'''
filename_replied_comments = "comments_replied_to.txt"

# getting id for posts replied to
if not os.path.isfile(filename_replied_posts):
    posts_replied_to = []
else:
    with open(filename_replied_comments, "r") as f:
        # read all posts ids splitting by new lines and remove nil values
        posts_replied_to = list(filter(None, f.read().split("\n")))
'''

reddit = praw.Reddit('bot1')
subreddits = reddit.subreddit(subreddits_to_search)

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
