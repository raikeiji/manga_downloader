#!/usr/bin/env python

#####################

import imghdr
import os
import re
import shutil
import sys
import urllib
import zipfile

#####################

from helper import *

#####################

class SiteParserBase:

	class AppURLopener(urllib.FancyURLopener):
		version = 'Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.472.14 Safari/534.3'
	
#####
	# something seriously wrong happened
	class FatalError(Exception):
		pass
	
	# typical misspelling of title and/or manga removal
	class MangaNotFound(Exception):
		pass
	
	# XML file config reports nothing to do
	class NoUpdates(Exception):
		pass
#####

	def __init__(self,optDict):
		urllib._urlopener = SiteParserBase.AppURLopener()
		for elem in vars(optDict):
			setattr(self, elem, getattr(optDict, elem))
		self.chapters = []
		self.chapters_to_download = []
		self.mangadl_tmp_path = 'mangadl_tmp'

	# this takes care of removing the temp directory after the last successful download
	def __del__(self):
		try:
			shutil.rmtree(self.mangadl_tmp_path)
		except:
			pass

#####
	def downloadChapters(self):
		raise NotImplementedError( 'Should have implemented this' )	
		
	def parseSite(self):
		raise NotImplementedError( 'Should have implemented this' )
#####
	
	def cleanTmp(self):
		"""
		Cleans the temporary directory in which image files are downloaded to and held in until they are compressed.
		"""
		
		print('Cleaning temporary directory...')
		
		try:
			# clean or create
			if os.path.exists(self.mangadl_tmp_path):
				shutil.rmtree(self.mangadl_tmp_path)
			os.mkdir(self.mangadl_tmp_path)
		except OSError:
			raise FatalError('Unable to create temporary directory.')
	
	def compress(self, manga_chapter_prefix, max_pages):
		"""
		Looks inside the temporary directory and zips up all the image files.
		"""
		
		print('Compressing...')
		
		zipPath = os.path.join(self.mangadl_tmp_path, manga_chapter_prefix + self.download_format)
		
		try:
			os.remove(zipPath)
		except OSError:
			pass
			
		z = zipfile.ZipFile( zipPath, 'w')
		
		for page in range(1, max_pages + 1):	
			temp_path = os.path.join(self.mangadl_tmp_path, manga_chapter_prefix + '_' + str(page).zfill(3))
			# we got an image file
			if imghdr.what(temp_path) != None:
				z.write( temp_path, manga_chapter_prefix + '_' + str(page).zfill(3) + '.' + imghdr.what(temp_path))
			# oh shit!
			else:
				raise FatalError('Warning: Site threw up garbage non-image page, possibly using anti-leeching heuristics.')
				
		z.close()
		
		# move the zipped file from the temporary directory to the specified download directory
		shutil.move( os.path.join(self.mangadl_tmp_path, manga_chapter_prefix + self.download_format), self.download_path)
		
	def downloadImage(self, page, pageUrl, manga_chapter_prefix, stringQuery):
		"""
		Given a page URL to download from, it searches using stringQuery as a regex to parse out the image URL, and downloads and names it using manga_chapter_prefix and page.
		"""
		
		# while loop to protect against server denies for requests
		# note that disconnects are already handled by getSourceCode, we use a regex to parse out the image URL and filter out garbage denies
		while True:
			try:
				source_code = getSourceCode(pageUrl)
				img_url = re.compile(stringQuery).search(source_code).group(1)
			except AttributeError:
				pass
			else:
				break

		# Line is encoding any special character in the URL must remove the http:// before encoding 
		# because otherwise the :// would be encoded as well				
		img_url = 'http://' + urllib.quote(img_url.split('//')[1])
		
		print(img_url)
		
		# while loop to protect against server denies for requests and/or minor disconnects
		while True:
			try:
				temp_path = os.path.join(self.mangadl_tmp_path, manga_chapter_prefix + '_' + str(page).zfill(3))
				urllib.urlretrieve(img_url, temp_path)
			except IOError:
				pass
			else:
				break
	
	def prepareDownload(self, current_chapter, queryString):
		"""
		Calculates some other necessary stuff before actual downloading can begin and does some checking.
		"""
		
		# clean now to make sure we start with a fresh temp directory
		self.cleanTmp()
		
		manga_chapter_prefix = fixFormatting(self.manga) + '_' + fixFormatting(self.chapters[current_chapter][1])
				
		zipPath = os.path.join(self.download_path,  manga_chapter_prefix + '.zip')
		cbzPath = os.path.join(self.download_path,  manga_chapter_prefix + '.cbz')	

		# we already have it
		if (os.path.exists(cbzPath) or os.path.exists(zipPath)) and self.overwrite_FLAG == False:
			print(self.chapters[current_chapter][1] + ' already downloaded, skipping to next chapter...')
			return (None, None, None)
		# overwriting
		else:
			for path in (cbzPath, zipPath):
				if os.path.exists(path):
					os.remove(path)
	
		# get the URL of the chapter homepage
		url = self.chapters[current_chapter][0]
		
		print(url)
		
		source_code = getSourceCode(url)
		
		# legacy code that may be used to calculate a series of image URLs
		# however, this is risky because some uploaders omit pages, double pages may also affect this
		# an alternative to this is os.walk through the temporary download directory
		# edit: this is actually required if you want a progress bar
		max_pages = int(re.compile(queryString).search(source_code).group(1))

		return (manga_chapter_prefix, url, max_pages)
	
	def selectChapters(self, chapters):
		"""
		Prompts user to select list of chapters to be downloaded from total list.
		"""
		
		# this is the array form of the chapters we want
		chapter_list_array_decrypted = []
		
		if(self.all_chapters_FLAG == False):
			chapter_list_string = raw_input('\nDownload which chapters?\n')
			
		if(chapter_list_string.lower() == 'all'):
			print('\nDownloading all chapters...')
			for i in range(0, len(chapters)):
				chapter_list_array_decrypted.append(i)
		else:
			# time to parse the user input
			
			#ignore whitespace, split using comma delimiters
			chapter_list_array = chapter_list_string.replace(' ', '').split(',')
			
			for i in chapter_list_array:
				iteration = re.search('([0-9]*)-([0-9]*)', i)
				
				# it's a range
				if(iteration is not None):
					for j in range((int)(iteration.group(1)), (int)(iteration.group(2)) + 1):
						chapter_list_array_decrypted.append(j - 1)
				# it's a single chapter
				else:
					chapter_list_array_decrypted.append((int)(i) - 1)
		return chapter_list_array_decrypted
	
	def selectFromResults(self, info):
		"""
		Basic error checking for manga titles, queries will return a list of all mangas that include the query, case-insensitively.
		"""
		
		found = False
		
		# info is a 2-tuple
		# info[0] contains a keyword or string that needs to be passed back (generally the URL to the manga homepage) and info[1] contains the manga name we'll be using
		# When asking y/n, we take a pessimistically only accept 'y'
		for notes in info:
			if notes[1].lower().find(self.manga.lower()) != -1:
				# manual mode
				if (not self.auto):
					print(notes[1])
				
				# exact match
				if notes[1].lower() == self.manga.lower():
					self.manga = notes[1]
					keyword = notes[0]
					found = True
					break
				else:
					# only request input in manual mode
					if (not self.auto):
						print('Did you mean: %s? (y/n)' % notes[1])
						answer = raw_input();
	
						if (answer == 'y'):
							self.manga = notes[1]
							keyword = notes[0]
							found = True
							break
		if (not found):
			raise self.MangaNotFound('No strict match found; please retype your query.\n')
		return keyword

########################################

class SiteParserFactory():
	"""
	Chooses the right subclass function to call.
	"""
	@staticmethod
	def getInstance(options):
		ParserClass = {
			'MangaFox' 	: MangaFoxParser,
			'MangaReader' 	: MangaReaderParser,
			'OtakuWorks' 	: OtakuWorksParser
		}.get(options.site, None)
		
		if not ParserClass:
			raise NotImplementedError( "Site Not Supported" )
		
		return ParserClass(options)

########################################
class MangaFoxParser(SiteParserBase):
	
	def parseSite(self):
		"""
		Parses list of chapters and URLs associated with each one for the given manga and site.
		"""
		
		print('Beginning MangaFox check...')
		
		url = 'http://www.mangafox.com/manga/%s/' % fixFormatting(self.manga)
		source_code = getSourceCode(url)
		
		# jump straight to expected URL and test if manga removed
		if(source_code.find('it is not available in Manga Fox.') != -1):
			raise self.MangaNotFound('Manga not found: it has been removed')
		
		# do a search
		url = 'http://www.mangafox.com/search.php?name=%s' % '+'.join(self.manga.split())
		try:
			source_code = getSourceCode(url)
			info = re.compile('a href="/manga/([^/]*)/[^"]*?" class=[^>]*>([^<]*)</a>').findall(source_code)
		# 0 results
		except AttributeError:
			raise self.MangaNotFound('Manga not found: it doesn\'t exist, or cannot be resolved by autocorrect.')
		else:	
			keyword = self.selectFromResults(info)
			url = 'http://www.mangafox.com/manga/%s/' % keyword
			source_code = getSourceCode(url)
			# other check for manga removal if our initial guess for the name was wrong
			if(source_code.find('it is not available in Manga Fox.') != -1):
				raise self.MangaNotFound('Manga not found: it has been removed')
		
			# that's nice of them
			url = 'http://www.mangafox.com/cache/manga/%s/chapters.js' % keyword
			source_code = getSourceCode(url)
		
			# chapters is a 2-tuple
			# chapters[0] contains the chapter URL
			# chapters[1] contains the chapter title
			self.chapters = re.compile('"(.*?Ch.[\d.]*)[^"]*","([^"]*)"').findall(source_code)

			# code used to both fix URL from relative to absolute as well as verify last downloaded chapter for XML component
			lowerRange = 0
		
			for i in range(0, len(self.chapters)):
				self.chapters[i] = ('http://www.mangafox.com/manga/%s/' % keyword + self.chapters[i][1], self.chapters[i][0])
				if (not self.auto):
					print('(%i) %s' % (i + 1, self.chapters[i][1]))
				else:
					if (self.lastDownloaded == self.chapters[i][1]):
						lowerRange = i + 1

			# this might need to be len(self.chapters) + 1, I'm unsure as to whether python adds +1 to i after the loop or not
			upperRange = len(self.chapters)
			
			# which ones do we want?
			if (not self.auto):
				self.chapters_to_download = self.selectChapters(self.chapters)
			# XML component
			else:
				if ( lowerRange == upperRange):
					raise self.NoUpdates
				
				for i in range (lowerRange, upperRange):
					self.chapters_to_download.append(i)
			return 		
	
	def downloadChapters(self):
		"""
		for loop that goes through the chapters we selected.
		"""
		
		### REMOVE THIS CODE? ###
		# if for some reason the name was never set...?
		# but it's always set now, via command-line arg and then updated later through info
		if (self.manga == None):
			raise self.MangaNotFound
			
		for current_chapter in self.chapters_to_download:
			manga_chapter_prefix, url, max_pages = self.prepareDownload(current_chapter, 'var total_pages=([^;]*?);')
			
			# more or less due to the MangaFox js script sometimes leaving up chapter names and taking down URLs
			if url == None:
				continue
			
			# download each image, basic progress indicator
			for page in range(1, max_pages + 1):
				print(self.chapters[current_chapter][1] + ' | ' + 'Page %i / %i' % (page, max_pages))
				pageUrl = '%s/%i.html' % (url, page)
				self.downloadImage(page, pageUrl, manga_chapter_prefix, ';"><img src="([^"]*)"')
			
			# zip them up
			self.compress(manga_chapter_prefix, max_pages)	

####################################################################
# The code for the other sites is similar enough to not need
# explanation, but dissimilar enough to not warrant any further OOP
####################################################################
class MangaReaderParser(SiteParserBase):

	def parseSite(self):
		print('Beginning MangaReader check...')
		
		url = 'http://www.mangareader.net/alphabetical'

		source_code = getSourceCode(url)
		info = re.compile('<li><a href="([^"]*)">([^<]*)</a>').findall(source_code[source_code.find('series_col'):])

		keyword = self.selectFromResults(info)
		url = 'http://www.mangareader.net%s' % keyword
		source_code = getSourceCode(url)
		
		self.chapters = re.compile('<tr><td><a href="([^"]*)" class="chico">([^<]*)</a>([^<]*)</td>').findall(source_code)
		
		lowerRange = 0
		
		for i in range(0, len(self.chapters)):
			self.chapters[i] = ('http://www.mangareader.net' + self.chapters[i][0], '%s%s' % (self.chapters[i][1], self.chapters[i][2]))
			if (not self.auto):
				print('(%i) %s' % (i + 1, self.chapters[i][1]))
			else:
				if (self.lastDownloaded == self.chapters[i][1]):
					lowerRange = i + 1
		
		# this might need to be len(self.chapters) + 1, I'm unsure as to whether python adds +1 to i after the loop or not
		upperRange = len(self.chapters)
						
		if (not self.auto):
			self.chapters_to_download = self.selectChapters(self.chapters)
		else:
			if ( lowerRange == upperRange):
				raise self.NoUpdates
			
			for i in range (lowerRange, upperRange):
				self.chapters_to_download .append(i)
		return 
	
	def downloadChapters(self):
		if (self.manga == None):
			raise self.MangaNotFound
				
		for current_chapter in self.chapters_to_download:
	
			manga_chapter_prefix, url, max_pages = self.prepareDownload(current_chapter, '</select> of (\d*)            </div>')
		
			if url == None:
				continue
			
			manga_chapter_prefix = fixFormatting(self.chapters[current_chapter][1])
			
			for page in re.compile("<option value='([^']*?)'[^>]*> (\d*)</option>").findall(getSourceCode(url)):
				print(self.chapters[current_chapter][1] + ' | ' + 'Page %s / %i' % (page[1], max_pages))
				pageUrl = 'http://www.mangareader.net' + page[0]
				self.downloadImage(page[1], pageUrl, manga_chapter_prefix, 'img id="img" src="([^"]*)"')
				
			self.compress(manga_chapter_prefix, max_pages)	

#############################################################			
class OtakuWorksParser(SiteParserBase):
	
	def parseSite(self):
		print('Beginning OtakuWorks check...')
		url = 'http://www.otakuworks.com/search/%s' % '+'.join(self.manga.split())

		source_code = getSourceCode(url)

		info = re.compile('a href="([^"]*?)"[^>]*?>([^<]*?) \(Manga\)').findall(source_code)
		if len(info) != 0:
			keyword = self.selectFromResults(info)
			source_code = getSourceCode(keyword)
	
		if(source_code.find('has been licensed and as per request all releases under it have been removed.') != -1):
			raise self.MangaNotFound('Manga not found: it has been removed.')
		
		self.chapters = re.compile('a href="([^>]*%s[^>]*)">([^<]*#[^<]*)</a>' % '-'.join(fixFormatting(self.manga).replace('_', ' ').split())).findall(source_code)
		self.chapters.reverse()

		lowerRange = 0
		for i in range(0, len(self.chapters)):
			self.chapters[i] = ('http://www.otakuworks.com' + self.chapters[i][0] + '/read', self.chapters[i][1])
			if (not self.auto):
				print('(%i) %s' % (i + 1, self.chapters[i][1]))
			else:
				if (self.lastDownloaded == self.chapters[i][1]):
					lowerRange = i + 1
		
		# this might need to be len(self.chapters) + 1, I'm unsure as to whether python adds +1 to i after the loop or not
		upperRange = len(self.chapters)	
	
		if (not self.auto):
			self.chapters_to_download = self.selectChapters(self.chapters)
		else:
			if ( lowerRange == upperRange):
				raise self.NoUpdates
			for i in range (lowerRange, upperRange):
				self.chapters_to_download.append(i)
		return 
		
	def downloadChapters(self):

		if (self.manga == None):
			raise self.MangaNotFound

		for current_chapter in self.chapters_to_download:
		
			manga_chapter_prefix, url, max_pages = self.prepareDownload(current_chapter, '<strong>(\d*)</strong>')
			if url == None:
				continue
		
			for page in range(1, max_pages + 1):
				print(self.chapters[current_chapter][1] + ' | ' + 'Page %i / %i' % (page, max_pages))
				pageUrl = '%s/%i' % (url, page)
				self.downloadImage(page, pageUrl, manga_chapter_prefix, 'img src="(http://static.otakuworks.net/viewer/[^"]*)"')
		
			self.compress(manga_chapter_prefix, max_pages)
			
#############################################################				
class AnimeaParser(SiteParserBase):

	##########
	#Animea check
	#	url = 'http://www.google.com/search?q=site:manga.animea.net+' + '+'.join(manga.split())
	#	source_code = urllib.urlopen(url).read()
	#	try:
	#		siteHome = re.compile('a href="(http://manga.animea.net/.*?.html)"').search(source_code).group(1)
	#	except AttributeError:
	#		total_chapters.append(0)
	#		keywords.append('')
	#	else:
	#		manga = re.compile('a href="http://manga.animea.net/(.*?).html"').search(source_code).group(1)
	#		url = siteHome
	#		source_code = urllib.urlopen(url).read()			
	#		total_chapters.append(int(re.compile('http://manga.animea.net/' + manga + '-chapter-(.*?).html').search(source_code).group(1)))
	#		keywords.append(manga)
	
	#	print('Finished Animea check.')
	#return (site, total_chapters)
	
	#	winningIndex = 1
	#	winningIndex = 0
	#	return (websites[0], keywords[winningIndex], misc[0])
	#	return (websites[winningIndex], keywords[winningIndex], chapters, chapter_list_array_decrypted)		
	##########

	def downloadAnimea(self, manga, chapter_start, chapter_end, download_path, download_format):
		for current_chapter in range(chapter_start, chapter_end + 1):	
			manga_chapter_prefix = manga.lower().replace('-', '_') + '_' + str(current_chapter).zfill(3)
			if (os.path.exists(download_path + manga_chapter_prefix + '.cbz') or os.path.exists(download_path + manga_chapter_prefix + '.zip')) and overwrite_FLAG == False:
				print('Chapter ' + str(current_chapter) + ' already downloaded, skipping to next chapter...')
				continue;
			url = 'http://manga.animea.net/'+ manga + '-chapter-' + str(current_chapter) + '-page-1.html'
			source_code = getSourceCode(url)
			max_pages = int(re.compile('of (.*?)</title>').search(source_code).group(1))
		
			for page in range(1, max_pages + 1):
				url = 'http://manga.animea.net/'+ manga + '-chapter-' + str(current_chapter) + '-page-' + str(page) + '.html'
				source_code = getSourceCode(url)
				img_url = re.compile('img src="(http.*?.[jp][pn]g)"').search(source_code).group(1)
				print('Chapter ' + str(current_chapter) + ' / ' + 'Page ' + str(page))
				print(img_url)
				downloadImage(img_url, os.path.join('mangadl_tmp', manga_chapter_prefix + '_' + str(page).zfill(3)))

			compress(manga_chapter_prefix, download_path, max_pages, download_format)