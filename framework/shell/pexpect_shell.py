#!/usr/bin/env python
'''
owtf is an OWASP+PTES-focused try to unite great tools and facilitate pen testing
Copyright (c) 2011, Abraham Aranguren <name.surname@gmail.com> Twitter: @7a_ http://7-a.org
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the copyright owner nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The shell module allows running arbitrary shell commands and is critical to the framework in order to run third party tools
The interactive shell module allows non-blocking interaction with subprocesses running tools or remote connections (i.e. shells)
'''
#import shlex
import pexpect, sys
from framework.lib.general import *
from framework.shell import blocking_shell 
from collections import defaultdict

class PExpectShell(blocking_shell.Shell):
	def __init__(self, Core):
		blocking_shell.Shell.__init__(self, Core) # Calling parent class to do its init part
		self.Connection = None
		self.Options = None
		self.CommandTimeOffset = 'PExpectCommand'
		
	def CheckConnection(self, AbortMessage):
		if not self.Connection:
			cprint("ERROR - Communication channel closed - " + AbortMessage)
			return False
		return True
		
	def Read(self, Time = 1):
		Output = ''
		if not self.CheckConnection('Cannot read'):
			return Output
		try:
			Output = self.Connection.after
			if Output == None:
				Output = ''
			print Output # Show progress on screen
		except pexpect.EOF:
			cprint("ERROR: Read - The Communication channel is down!")
			return Output  # End of communication channel
		return Output
	
	def FormatCommand(self, Command):
		#print "self.Options['RHOST']=" + str(self.Options['RHOST']) + "self.Options['RPORT']=" + str(self.Options['RPORT']) + "Command=" + str(Command)
		if "RHOST" in self.Options and 'RPORT' in self.Options: # Interactive shell on remote connection
			return self.Options['RHOST'] + ':' + self.Options['RPORT'] + ' - ' + Command
		else:
			return "Interactive - " + Command
	
	def Run(self, Command):
		Output = ''
		Cancelled = False
		if not self.CheckConnection("NOT RUNNING Interactive command: " + Command):
			return Output
		# TODO: tail to be configurable: \n for *nix, \r\n for win32
		LogCommand = self.FormatCommand(Command)
		CommandInfo = self.StartCommand(LogCommand, LogCommand)
		try:
			cprint("Running Interactive command: " + Command)
			#SendAll(self.Connection, Command + "\n")
			self.Connection.sendline(Command)
			#Output += self.Read()
			self.FinishCommand(CommandInfo, Cancelled)
		except pexpect.EOF:
			Cancelled = True
			cprint("ERROR: Run - The Communication Channel is down!")
			self.FinishCommand(CommandInfo, Cancelled)
		except KeyboardInterrupt:
			Cancelled = True
			self.FinishCommand(CommandInfo, Cancelled)
			Output += self.Core.Error.UserAbort('Command', Output) # Identify as Command Level abort
		if not Cancelled:
			self.FinishCommand(CommandInfo, Cancelled)
		return Output
	
	def Expect(self, Pattern, TimeOut = -1):
		if self.Connection == None:
			return False
		try:
			self.Connection.expect(Pattern, TimeOut)
		except pexpect.EOF:
			cprint("ERROR: Expect - The Communication Channel is down!")
		except pexpect.TIMEOUT:
			cprint("ERROR: Expect timeout threshold exceeded for pattern '" + Pattern + "'!")
			cprint("Before:")
			print self.Connection.after
			cprint("After:")
			print self.Connection.after
		return True
		
	def RunCommandList(self, CommandList):
			Output = ""
			for Command in CommandList:
				Output += self.Run(Command)
			return Output

	def Open(self, Options, PluginInfo):
		self.Options = Options # Store Options for Closing processing
		Output = ''
		if not self.Connection:
			CommandList = [ 'bash' ]
			if 'ConnectVia' in Options:
				Name, Command = Options['ConnectVia'][0]
				CommandList += Command.split(";")
			CmdCount = 1
			for Cmd in CommandList:
				if CmdCount == 1:
					self.Connection = pexpect.spawn(Cmd)					
					self.Connection.logfile = sys.stdout # Ensure screen feedback
				else:
					self.Run(Cmd)
				CmdCount += 1
			if 'InitialCommands' in Options and Options['InitialCommands']:
				Output += self.RunCommandList(Options['InitialCommands'])
			#Output += self.Read()
		#Output += self.Read()
		return Output
	
	def Kill(self):
		cprint("Killing Communication Channel..")
		self.Connection.kill(0)
		self.Connection = None
		
	def Wait(self):
		cprint("Waiting for Communication Channel to close..")
		self.Connection.wait()
		self.Connection = None
		
	def Close(self, PluginInfo):
		if self.Connection == None:
			cprint("Close: Connection already closed")
			return False
		if 'CommandsBeforeExit' in self.Options and self.Options['CommandsBeforeExit']:
			cprint("Running commands before closing Communication Channel..")
			self.RunCommandList(self.Options['CommandsBeforeExit'].split(self.Options['CommandsBeforeExitDelim']))
			#self.RunCommandList(self.Options['CommandsBeforeExit'].split('#'))
		cprint("Trying to close Communication Channel..")
		self.Run("exit")
		
		if 'ExitMethod' in self.Options and self.Options['ExitMethod'] == 'kill':
			self.Kill()
		else: # By default wait
			self.Wait()
		#self.Read()
		#self.Connection = None
		#self.Connection.stdin = "exit\r"
		#self.Connection.wait()
		#self.Connection.kill()
		#return Core.PluginHelper.DrawCommandDump('Init Channel Command', 'Output', Core.Config.GetResources(Resource), PluginInfo, "") # No previous output
	
	def IsClosed(self):
		return self.Connection == None