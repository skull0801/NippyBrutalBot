from nippy_bot import NippyBot, log
import time

subs = 'dota2+globaloffensive+overwatch+hearthstone+leagueoflegends'

stdout = open('logs/out.txt', 'a')
stderr = open('logs/err.txt', 'a')

bot = NippyBot(bot_name="NippyBrutalBot",
               praw_bot_name='bot1',
               subreddits_to_search=subs,
               post_age_limit=60*60*3,
               db_file='database.db',
               verbose=True)


log(time.strftime("Start time: %a %Y-%m-%d %H:%M:%S", time.localtime()))
log("Searching for rising, new and controversial comments in /r/{}".format(subs))
submissions = bot.get_submissions(new=100, rising=25, controversial=25)
result = bot.parse_submissions(submissions)
log("All operations done. {} submissions checked. {} comments checked. {} comments matched. {} comments invalidated. {} comments replied to. {} comments saved for later. {} submissions replied to.".format(len(submissions), result[0], result[1], result[1] - result[2], result[2], result[3], result[4]))
log(time.strftime("End time: %a %Y-%m-%d %H:%M:%S", time.localtime()))
log("---------------------------------")
bot.finish()

stdout.close()
stderr.close()
