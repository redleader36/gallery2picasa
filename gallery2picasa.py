#!/usr/bin/env python

from modules import db
from modules import flags
from modules import items
from modules import utils

import gdata.photos
import gdata.photos.service
import gdata.media
import gdata.geo
import getopt
import sys
import time
import mimetypes
import getpass

FLAGS = flags.FLAGS
FLAGS.AddFlag('b', 'dbuser', 'The username to use for the database')
FLAGS.AddFlag('a', 'dbpass', 'The password to use for the database (interactive prompt if unspecified)', '')
FLAGS.AddFlag('d', 'database', 'The database to use', 'gallery2')
FLAGS.AddFlag('h', 'hostname', 'The database hostname', 'localhost')
FLAGS.AddFlag('t', 'table_prefix', 'The table prefix to use', 'g2_')
FLAGS.AddFlag('f', 'field_prefix', 'The field prefix to use', 'g_')
FLAGS.AddFlag('u', 'username', 'The Google username to use')
FLAGS.AddFlag('p', 'password', 'The Google password to use (interactive prompt if unspecified)', '')
FLAGS.AddFlag('y', 'privacy', 'The access level for the album ("private" or "public")', 'private')
FLAGS.AddFlag('o', 'confirm', 'Confirm upload for every album', 'true')
FLAGS.AddFlag('x', 'exclude_movies', 'Exclude movies from the upload', 'false')
FLAGS.AddFlag('n', 'dry_run', 'Do not upload, just print what would be uploaded', 'false')
FLAGS.AddFlag('g', 'gallery_prefix', 'Prefix for gallery photos',
    '/var/local/g2data')
FLAGS.AddFlag('l', 'long_titles', 'Construct long album titles using parents\' titles', 'false')
FLAGS.AddFlag('c', 'truncate_count',
    'Truncate this many album names from long titles. To be used with -l.',
     '0')
FLAGS.AddFlag('s', 'single_album', 'Only upload this single album (by name)')

# Error avoidance
retry = 10            # Number of retries
delay = 0.2           # Delay in (sub-)seconds
backoff = 2           # Double delay on every retry
max_per_album = 1000  # Maximum items per album

# Grabbed from http://code.google.com/intl/de-DE/apis/picasaweb/docs/2.0/developers_guide_protocol.html
valid_mimetypes = [
'image/bmp',
'image/gif',
'image/jpeg',
'image/png',
'video/3gpp',
'video/avi',
'video/quicktime',
'video/mp4',
'video/mpeg',
'video/mpeg4',
'video/msvideo',
'video/x-ms-asf',
'video/x-ms-wmv',
'video/x-msvideo'
]

if sys.stdout.isatty():
    default_encoding = sys.stdout.encoding
else:
    import locale
    default_encoding = locale.getpreferredencoding()

# Hack because python gdata client does not accept videos?!
for mtype in valid_mimetypes:
  mayor, minor = mtype.split('/')
  if mayor == 'video':
    gdata.photos.service.SUPPORTED_UPLOAD_TYPES += (minor,)

def create_google_album(pws, album, atitle, privacy, seq=0):
  summary = album.summary() or album.description()
  timestamp = None
  if album.created() > 0:
    # Google expects creation timestamp in microseconds and as a string parameter
    timestamp = '%s000' % album.created()
  if seq > 0:
    atitle = "%s_%s" % (atitle, seq)
  mtries, mdelay = retry, delay
  while mtries > 0:
    if mtries != retry:
      strout = 'Retrying album creation.'
      print strout.encode(default_encoding, 'replace')
    try:
      strout = 'CREATING ALBUM [%s] [%s]' % (atitle, summary)
      print strout.encode(default_encoding, 'replace')
      if FLAGS.dry_run == 'true':
        return True
      return pws.InsertAlbum(atitle, summary, access=privacy, timestamp=timestamp)
    except gdata.photos.service.GooglePhotosException, e:
      if e[0] < 500:
        raise e
      strout = 'Google error: gdata.photos.service.GooglePhotosException %s' % e
      print strout.encode(default_encoding, 'replace')
    mtries -=1
    strout = 'Sleeping %.2f seconds.' % mdelay
    print strout.encode(default_encoding, 'replace')
    time.sleep(mdelay)
    mdelay *= backoff
  raise Exception('Could not create album')

def album_title_with_parents(albums, leaf_album, truncate):
  titles = [leaf_album.title()]
  parent_id = leaf_album.parent_id()
  while parent_id:
    album = albums[parent_id]
    titles.insert(0, album.title())
    parent_id = album.parent_id()

  for unused in xrange(truncate):
    if len(titles) > 1:
      titles.pop(0)
  
  return ' - '.join(titles)

def main(argv):
  appname = argv[0]

  try:
    argv = FLAGS.Parse(argv[1:])
  except flags.FlagParseError, e:
    utils.Usage(appname, e.usage(), e.message())
    sys.exit(1)

  if FLAGS.dbpass == '':
    FLAGS.dbpass = getpass.getpass('DB Password:')

  if FLAGS.password == '':
    FLAGS.password = getpass.getpass('Google Password:')

  gdb = db.Database(FLAGS.dbuser, FLAGS.dbpass, FLAGS.database,
      FLAGS.hostname, FLAGS.table_prefix, FLAGS.field_prefix)

  pws = gdata.photos.service.PhotosService()
  if FLAGS.dry_run != 'true':
    # pws.ClientLogin(FLAGS.username, FLAGS.password)
    pws.email = FLAGS.username
    pws.password = FLAGS.password
    pws.source = 'Redleader36-Gallery2Picasa'
    pws.ProgrammaticLogin()

  confirm = FLAGS.confirm
  if confirm == 'true':
      confirm = True
  else:
      confirm = False

  try:
    albums = {}
    albumlist = []
    album_ids = gdb.ItemIdsForTable(items.AlbumItem.TABLE_NAME)
    for id in album_ids:
      albums[id] = items.AlbumItem(gdb, id)
    for id in album_ids:
      albumlist += (id, album_title_with_parents(albums, albums[id], int(FLAGS.truncate_count))),

    albumlist = sorted(albumlist, key=lambda album: album[1] )

    child_entities = {}
    child_ids = gdb.ItemIdsForTable(items.ChildEntity.TABLE_NAME)
    for id in child_ids:
      child = items.ChildEntity(gdb, id)
      child_entities[id] = child

    comments_by_photo = {}
    comment_ids = gdb.ItemIdsForTable(items.Comment.TABLE_NAME)
    for id in comment_ids:
      comment = items.Comment(gdb, id)
      child = child_entities.get(id)
      if child:
        photo_id = child.parent_id()
        if photo_id not in comments_by_photo:
          comments_by_photo[photo_id] = []
        comments_by_photo[photo_id].append(comment)

    derivatives_by_photo = {}
    derivative_ids = gdb.ItemIdsForTable(items.Derivative.TABLE_NAME)
    for id in derivative_ids:
      derivative = items.Derivative(gdb, id)
      if derivative.source_id() not in derivatives_by_photo:
        derivatives_by_photo[derivative.source_id()] = []
      derivatives_by_photo[derivative.source_id()].append(derivative)

    photos_by_album = {}
    photo_ids = gdb.ItemIdsForTable(items.PhotoItem.TABLE_NAME)
    for id in photo_ids:
      photo = items.PhotoItem(gdb, id)
      if photo.parent_id() not in photos_by_album:
        photos_by_album[photo.parent_id()] = []

      derivatives = derivatives_by_photo.get(id)
      for derivative in derivatives:
        operation = derivative.operations()
        if operation.startswith('rotate'):
            rotation = operation.split('|')[1]
            photo.set_rotation(rotation)

      comments = comments_by_photo.get(id, [])
      for comment in comments:
          photo.add_comment(comment)

      photos_by_album[photo.parent_id()].append(photo)

    if FLAGS.exclude_movies != 'true':
      movie_ids = gdb.ItemIdsForTable(items.MovieItem.TABLE_NAME)
      for id in movie_ids:
        movie = items.MovieItem(gdb, id)
        if movie.parent_id() not in photos_by_album:
          photos_by_album[movie.parent_id()] = []
        photos_by_album[movie.parent_id()].append(movie)

    albums_to_upload = albums.copy()

    if confirm:
      for album in albumlist:
        if album[0] not in photos_by_album:
          continue

        upload_album = False
        confirmed = False
        while confirmed == False:
          if FLAGS.single_album:
            if FLAGS.single_album == album[1]:
              upload_album = True
            confirmed = True
            continue
          confirm_input = raw_input('Upload Album "%s"? [y/N/a]' % album[1].encode(default_encoding, 'replace')).lower()
          if confirm_input == 'n' or confirm_input == '':
            confirmed = True
          elif confirm_input == 'y':
            upload_album = True
            confirmed = True
          elif confirm_input == 'a':
            upload_album = True
            confirm = False
            confirmed = True

        if upload_album != True:
          del albums_to_upload[album[0]]

        if confirm == False:
            break

    for album_id,_ in albumlist:
      if album_id not in photos_by_album or album_id not in albums_to_upload:
        continue
      album = albums[album_id]
      atitle = album.title()
      if FLAGS.long_titles == 'true':
        atitle = album_title_with_parents(albums, album, int(FLAGS.truncate_count))

      privacy = FLAGS.privacy.lower()
      if privacy != 'public':
        privacy = 'private'

      galbum = create_google_album(pws, album, atitle, privacy)

      pcount = 0
      acount = 0
      for photo in photos_by_album[album.id()]:
        filename = '%s/albums/%s/%s' % (
            FLAGS.gallery_prefix, album.full_album_path(gdb), photo.path_component())
        (filetype, fileenc) = mimetypes.guess_type(filename)
        if filetype not in valid_mimetypes:
            strout = '%s has no valid MIME-Type!' % photo.path_component()
            print strout.encode(default_encoding, 'replace')
            continue

        pcount += 1
        if pcount > max_per_album:
          pcount = 1
          acount += 1
          galbum = create_google_album(pws, album, atitle, privacy, acount)

        # Title is displayed nowhere in picasa?
        title = photo.title() or photo.path_component()
        summary = photo.summary() or photo.description() or photo.title()

        if photo.title() and photo.summary() and photo.description():
            print("Warning: title, summary and description used. Description is merged with summary!")
            summary = photo.summary() + photo.description()
  
        keywords = ', '.join(photo.keywords().split())

        mtries, mdelay = retry, delay
        success = False
        while mtries > 0:
          if mtries != retry:
            strout = 'Retrying media upload.'
            print strout.encode(default_encoding, 'replace')
          try:
            strout = '\tCREATING Item [F:%s] [T:%s] [S:%s] [K:%s]' % (
                photo.path_component(), title, summary, photo.keywords())
            print strout.encode(default_encoding, 'replace')
            if FLAGS.dry_run != 'true':
              pws_photo = pws.InsertPhotoSimple(galbum.GetFeedLink().href, title,
                summary, filename, keywords=keywords, content_type=filetype)

            if photo.rotation():
              print "Rotating photo by %s degrees" % photo.rotation()
              if FLAGS.dry_run != 'true':
                  pws_photo.rotation = gdata.photos.Rotation(text=rotation)
                  pws_photo = pws.UpdatePhotoMetadata(pws_photo)

            for comment in photo.comments():
              if FLAGS.dry_run != 'true':
                  pws.InsertComment(photo, comment)

            success = True
            break
          except gdata.photos.service.GooglePhotosException, e:
            if e[0] in [500, 503]:
              strout = 'Google error: gdata.photos.service.GooglePhotosException %s' % e
              print strout.encode(default_encoding, 'replace')
            # Error 413: Entity too large
            elif e[0] in [413]:
              strout = 'Google error: Entity too large!'
              print strout.encode(default_encoding, 'replace')
              # Continue with next photo
              success = 1
              break
            else:
              raise e
          mtries -=1
          strout = 'Sleeping %.2f seconds.' % mdelay
          print strout.encode(default_encoding, 'replace')
          time.sleep(mdelay)
          mdelay *= backoff
        if not success:
          raise Exception('Could not upload photo')

  finally:
    gdb.close()

if __name__ == '__main__':
  main(sys.argv)
