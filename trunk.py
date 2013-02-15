#!/usr/bin/env python2.7
import logging
import os
import sys

from application.notification import NotificationCenter, IObserver
from optparse import OptionParser
from threading import Event
from zope.interface import implements

from sipsimple.account import AccountManager, Account
from sipsimple.application import SIPApplication
from sipsimple.audio import WavePlayer
from sipsimple.configuration.datatypes import SIPProxyAddress
from sipsimple.configuration.settings import SIPSimpleSettings
from sipsimple.core import SIPURI, SIPCoreError, ToHeader, Route
from sipsimple.session import Session, SessionManager
from sipsimple.streams import AudioStream
from sipsimple.storage import MemoryStorage
from sipsimple.threading.green import run_in_green_thread

class SIPEngineLogObserver(object):
	implements(IObserver)
	
	def handle_notification(self, notification):
		logging.info("(%(level)d) %(sender)14s: %(message)s" % notification.data.__dict__)

class SimpleCallApplication(SIPApplication):
	def __init__(self):
		SIPApplication.__init__(self)
		self.player = None
		self.ended = Event()
		self.logeng = SIPEngineLogObserver()

		notification_center = NotificationCenter()
		notification_center.add_observer(self)
		notification_center.add_observer(self.logeng, name="SIPEngineLog")

		SIPSimpleSettings.sip.udp_port=5060
		SIPSimpleSettings.sip.transport_list=['udp']

	# Application Events
	@run_in_green_thread
	def _NH_SIPApplicationDidStart(self, notification):
		logging.info("Application started")

		# configure our account
		self.my_account = Account("*@62.220.30.149")
		self.my_account.sip.register = False
		self.my_account.enabled = True
		self.my_account.save()
	
	def _NH_SIPApplicationDidEnd(self, notification):
		logging.info("Application ended")
		self.ended.set()
		
	# Account Events
	def _NH_SIPAccountWillActivate(self, notification):
		logging.info("Account Activating!")
	
	def _NH_SIPAccountDidActivate(self, notification):
		logging.info("Account Activated!")
	
	# Session Events
	@run_in_green_thread
	def _NH_SIPSessionNewIncoming(self, notification):
		logging.info("Incoming")
		
		# lets accept it
		session = notification.sender
		session.send_ring_indication()
		session.accept([AudioStream()])

	def _NH_SIPSessionWillStart(self, notification):
		logging.info("Session will start")

	def _NH_SIPSessionGotRingIndication(self, notification):
		logging.info('Ringing!')

	def _NH_SIPSessionDidStart(self, notification):
		session = notification.sender
		logging.info('Session started - Local: %s - Remote: %s', str(session.local_identity), str(session.remote_identity))

		session.my_player = WavePlayer(SIPApplication.voice_audio_mixer, "/root/Sleep Away.wav", loop_count=0, initial_play=False)
		audio_stream = session.streams[0]
		audio_stream.bridge.add(session.my_player)
		session.my_player.play()

	def _NH_SIPSessionDidFail(self, notification):
		logging.info('Failed to connect')

	def _NH_SIPSessionWillEnd(self, notification):
		logging.info('Session will end')
		session = notification.sender

		session.my_player.stop()
		audio_stream = session.streams[0]
		audio_stream.bridge.remove(session.my_player)

	def _NH_SIPSessionDidEnd(self, notification):
		logging.info('Session ended')

	def _NH_SIPSessionDidProcessTransaction(self, notification):
		logging.info('Transaction processed - method: %s - code: %s -  reason: %s' % (notification.data.method, notification.data.code, notification.data.reason))


if __name__ == '__main__':
	# setup logging
	logging.basicConfig(format='%(asctime)-15s %(message)s', level=logging.DEBUG)
	
	# setup app
	application = SimpleCallApplication()
	application.start(MemoryStorage())
	
	# wait for it
	logging.error("---Press Enter to quit the program")
	raw_input()
	logging.info("---Shutting down")
	
	# end it
	application.stop()
	application.ended.wait()
