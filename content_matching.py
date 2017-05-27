import praw
import re

class ContentMatch:
    def next(self):
        return None

    def has_next(self):
        return False

    def current_id(self):
        return ''

    def reset(self):
        pass

class SubmissionContent(ContentMatch):
    def __init__(self, submission):
        self.submission = submission
        self.prepare()

    def prepare(self):
        content = [self.submission.selftext, self.submission.title, self.submission.url]
        self.values = content
        self.index = -1

    def has_next(self):
        return self.index < len(self.values) - 1

    def next(self):
        if self.has_next():
            self.index = self.index + 1
            return self.values[self.index]

    def current_id(self):
        return self.submission.name

    def reset(self):
        self.index = -1

class CommentContent(ContentMatch):
    def __init__(self, comment):
        self.comment = comment
        self.current_comment = comment
        self.started = False

    def has_next(self):
        return not self.started or not self.current_comment.is_root

    def next(self):
        if self.started:
            if self.current_comment.is_root:
                return None
            self.current_comment = self.current_comment.parent()
        else:
            self.started = True
            self.current_comment = self.comment
        return self.current_comment.body

    def current_id(self):
        return self.current_comment.id

    def reset(self):
        self.started = False
        self.current_comment = self.comment

class ContentMatcher:
    #pattern should be a tuple with the pattern to match, the sanitizer string (None for no sanitizing), and max_size (0 for no max)
    def __init__(self, patterns, ignore_case=True):
        self.patterns = patterns
        self.ignore_case = ignore_case

    def match(self, content):
        n = content.next()
        if n is None:
            return None
        for pattern, sanitizer, max_size in self.patterns:
            match = self.match_with_pattern(n, pattern, max_size)
            if match:
                return [(self.sanitize(match, sanitizer), content.current_id())]

    def match_with_pattern(self, content, pattern, max_size):
        flags = re.IGNORECASE if self.ignore_case else 0
        if max_size > 0 and len(content) > max_size:
            return None
        match = re.search(pattern, content, flags)
        if match:
            return match[0]
        else:
            return None

    def sanitize(self, string, sanitizer=None):
        if sanitizer:
            return re.sub(sanitizer, '', string)
        else:
            return string


class ChainContentMatcher(ContentMatcher):
    def __init__(self, patterns, ignore_case=True):
        self.patterns = patterns
        self.ignore_case = ignore_case

    def match(self, content):
        result = []
        for pattern, sanitizer, max_size in self.patterns:
            n = content.next()
            if n is None:
                return None
            match = self.match_with_pattern(n, pattern, max_size)
            if match:
                result.append((self.sanitize(match, sanitizer), content.current_id()))
            else: # cancel search because one of the contents does not match
                return None
        return result
