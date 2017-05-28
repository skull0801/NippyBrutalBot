from nippy_bot import NippyBot, log
import time

subs = 'dota2+globaloffensive+overwatch+hearthstone+leagueoflegends'
subs = 'skull0801devtest'

stdout = open('logs/out_new.txt', 'a')
stderr = open('logs/err_new.txt', 'a')

bot = NippyBot(bot_name="NippyBrutalBot",
               praw_bot_name='bot1',
               subreddits_to_search=subs,
               post_age_limit=60*60*3,
               db_file='database.db',
               verbose=True,
               dry_run=True)


limit = 1500

log(time.strftime("Start time: %a %Y-%m-%d %H:%M:%S", time.localtime()))
log("Searching for {} newest comments in /r/{}".format(limit, subs))
comments = bot.get_comments_from_sub(subs, limit)
result = bot.parse_comments(comments, commit=True)
submissions = bot.get_submissions(new=100)
result2 = bot.parse_submissions(submissions, check_comments=False)
log("All operations done. {} comments checked. {} comments matched. {} comments invalidated. {} comments replied to. {} comments saved for later.".format(result[0], result[1], result[1] - result[2], result[2], result[3]))
log("{} submissions checked. {} submissions replied to.".format(len(submissions), result2[4]))
log(time.strftime("End time: %a %Y-%m-%d %H:%M:%S", time.localtime()))
log("---------------------------------")
bot.finish()

stdout.close()
stderr.close()
