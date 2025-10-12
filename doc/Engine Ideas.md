# Engine ideas
## VM descriptor

The descriptor object stores:
 - Its own local config
 - In 
 -

 - If a operation is being executed, only for async tasks. Only in memory, not saved on disk.
 


A command has a target object, or more than one, e.g., some VM descriptors.



I am thinking in this: When a client sends a command ( any kind), inernally, a command object is created, with a unique command number. It is an async operation, usually. So It returns the command number, and a message like "pending". The engine tries to execute the command.
For the sync commands: return the result, or warning or error.
For async commands: when done, store the result in a Results Queue.
 If success, it stores the result in the Executed commands Queue. Also a small line to the log, just with the metadata of the command