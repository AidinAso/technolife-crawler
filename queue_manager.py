from collections import deque

class URLQueue:
    #create a empty queue
    def __init__(self):
        self.queue = deque()

    #add a url to end queue
    def enqueue(self, url):
        self.queue.append(url)

    #remove a url from front queue
    def dequeue(self):
        if not self.is_empty():
            return self.queue.popleft()
        else:
            return None

    #check if queue is empty
    def is_empty(self):
        return len(self.queue) == 0

    #get the size of the queue
    def size(self):
        return len(self.queue)