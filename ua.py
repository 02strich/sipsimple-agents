#!/usr/bin/env python2.7
import logging
import os
import random
import sys
import time

from application.notification import NotificationCenter
from threading import Event

from sipsimple.account import AccountManager, Account
from sipsimple.application import SIPApplication
from sipsimple.audio import WavePlayer
from sipsimple.configuration.datatypes import SIPProxyAddress
from sipsimple.configuration.settings import SIPSimpleSettings
from sipsimple.core import SIPURI, SIPCoreError, ToHeader, Route
from sipsimple.session import Session
from sipsimple.streams import AudioStream
from sipsimple.storage import MemoryStorage
from sipsimple.threading.green import run_in_green_thread


class SimpleCallApplication(SIPApplication):
	def __init__(self):
		SIPApplication.__init__(self)
		
		# events used through out lifecycle
		self.ended = Event()
		self.started = Event()
		self.registering = Event()
		
		# normal properties
		self.accounts = {}
		self.active_sessions = []
		
		# configure notifications
		notification_center = NotificationCenter()
		notification_center.add_observer(self)
		
		# lets get this thing rolling
		self.start(MemoryStorage())
		
		# wait for it to finish
		self.started.wait()
	
	def add_account(self, name, username, password):
		if name in self.accounts:
			raise Exception("Already got account with that name")
		
		logging.info("adding account: %s", name)
		
		# clear the event, in case something went wrong
		self.registering.clear()
		
		# register/create the account
		new_account = Account(name)
		new_account.auth.username = username
		new_account.auth.password = password
		new_account.sip.register_interval = 30
		new_account.enabled = True
		new_account.save()
		
		# wait for it to be completly created
		self.registering.wait()
		
		# remember our account
		self.accounts[name] = new_account
	
	def call(self, account_name, callee, wave_file, length=None):
		logging.info("calling from: %s - to: %s", account_name, callee)
		# Setup wave playback
		self.player = WavePlayer(SIPApplication.voice_audio_mixer, wave_file, loop_count=0, initial_play=False)
		
		# configure callee and route to him/her
		callee_header = ToHeader(SIPURI.parse(callee))
		routes = [Route("62.220.31.184", 5060, "udp")]
		
		# locate caller
		account = self.accounts.get(account_name, None)
		if account is None:
			raise Exception("No account with that name found")
		
		# finally make the call
		session = Session(account)
		session.connect(callee_header, routes, [AudioStream()])
		
		# if we got a length, end the call after it
		if not length is None:
			time.sleep(length)
			session.end()
	
	# ----------------------------
	# Application Events
	# ----------------------------
	@run_in_green_thread
	def _NH_SIPApplicationDidStart(self, notification):
		logging.info("Application started")
		self.started.set()
	
	def _NH_SIPApplicationDidEnd(self, notification):
		logging.info("Application ended")
		self.ended.set()
	
	# ----------------------------
	# Account Events
	# ----------------------------
	def _NH_SIPAccountWillActivate(self, notification):
		logging.info("Activating!")
	
	def _NH_SIPAccountDidActivate(self, notification):
		logging.info("Activated!")
		self.registering.set()
	
	# ----------------------------
	# Session Events
	# ----------------------------
	def _NH_SIPSessionGotRingIndication(self, notification):
		logging.info('Ringing!')

	def _NH_SIPSessionDidStart(self, notification):
		logging.info('Session started!')
		session = notification.sender
		audio_stream = session.streams[0]
		audio_stream.bridge.add(self.player)
		self.player.play()

	def _NH_SIPSessionDidFail(self, notification):
		logging.info('Failed to connect')
		self.stop()

	def _NH_SIPSessionWillEnd(self, notification):
		logging.info("Session will end")
		session = notification.sender
		audio_stream = session.streams[0]
		self.player.stop()
		audio_stream.bridge.remove(self.player)

	def _NH_SIPSessionDidEnd(self, notification):
		logging.info('Session ended')
	
	def _NH_SIPSessionDidProcessTransaction(self, notification):
		logging.info('Transaction processed - method: %s - code: %s -  reason: %s' % (notification.data.method, notification.data.code, notification.data.reason))


if __name__ == '__main__':
	# setup app
	application = SimpleCallApplication()
	
	# register accounts
	for i in range(200,221):
		application.add_account("%d@62.220.31.184" % i, str(i), "test123")
		
	# make some calls
	for i in range(1, 10):
		account = "%d@62.220.31.184" % random.randint(200,220)
		target = "sip:%d@62.220.31.184" % random.randint(1000, 9999)
		application.call(account, target, '/home/stefan/Desktop/Sleep Away.wav', 10)
	
	# end it
	application.stop()
	#application.ended.wait()



