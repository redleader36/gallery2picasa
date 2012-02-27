from modules import utils
import os
import datetime

class Item(object):
  TABLE_NAME = 'Item'

  def __init__(self, db, id):
    try:
      if id == self.__id:
        return
    except AttributeError, e:
      pass

    self.__id = id
    (description, keywords, summary, title, created) = db.FieldsForItem(
        id, Item.TABLE_NAME, 'description', 'keywords', 'summary', 'title', 'originationTimestamp')

    self.__description = utils.HtmlUnescape(
        (description, '')[description is None])
    self.__keywords = utils.HtmlUnescape((keywords, '')[keywords is None])
    self.__summary = utils.HtmlUnescape((summary, '')[summary is None])
    self.__title = utils.HtmlUnescape((title, '')[title is None])
    self.__created = created
    self.__rotation = None
    self.__comments = []

  def __str__(self):
    return "%s: title='%s' created='%s' summary='%s' description='%s' keywords='%s'" % (
      self.type(), self.__title,
      datetime.datetime.strftime(datetime.datetime.fromtimestamp(self.__created), '%Y-%m-%d %H:%M'),
      self.__summary, self.__description, self.__keywords)

  def type(self):
    pass

  def id(self):
    return self.__id

  def description(self):
    return self.__description

  def keywords(self):
    return self.__keywords

  def summary(self):
    return self.__summary

  def title(self):
    return self.__title

  def created(self):
    return self.__created

  def rotation(self):
    return self.__rotation

  def comments(self):
    return self.__comments

  def add_comment(self, comment):
    self.__comments.append(comment)

  def set_rotation(self, rotation):
    self.__rotation = rotation

class ChildEntity(Item):
  TABLE_NAME = 'ChildEntity'

  def __init__(self, db, id):
    (parent_id,) = db.FieldsForItem(id, ChildEntity.TABLE_NAME, 'parentId')
    self.__parent_id = None
    if parent_id > 0:
      self.__parent_id = parent_id

  def parent_id(self):
    return self.__parent_id


class FileSystemEntity(Item):
  TABLE_NAME = 'FileSystemEntity'

  def __init__(self, db, id):
    Item.__init__(self, db, id)
    (path_component,) = db.FieldsForItem(
        id, FileSystemEntity.TABLE_NAME, 'pathComponent')
    self.__path_component = path_component

  def path_component(self):
    return self.__path_component


class PhotoItem(ChildEntity, FileSystemEntity):
  TABLE_NAME = 'PhotoItem'

  def __init__(self, db, id):
    ChildEntity.__init__(self, db, id)
    FileSystemEntity.__init__(self, db, id)
    self.__id = id
    (width, height) = db.FieldsForItem(
        id, PhotoItem.TABLE_NAME, 'width', 'height')
    self.__width = width
    self.__height = height

  def type(self):
    return 'Photo'

  def width(self):
    return self.__width

  def height(self):
    return self.__height

class MovieItem(ChildEntity, FileSystemEntity):
  TABLE_NAME = 'MovieItem'

  def __init__(self, db, id):
    ChildEntity.__init__(self, db, id)
    FileSystemEntity.__init__(self, db, id)
    self.__id = id
    (width, height, duration) = db.FieldsForItem(
        id, MovieItem.TABLE_NAME, 'width', 'height', 'duration')
    self.__width = width
    self.__height = height
    self.__duration = duration

  def type(self):
    return 'Movie'

  def width(self):
    return self.__width

  def height(self):
    return self.__height

  def duration(self):
    return self.__duration

class AlbumItem(ChildEntity, FileSystemEntity):
  TABLE_NAME = 'AlbumItem'

  def __init__(self, db, id):
    ChildEntity.__init__(self, db, id)
    FileSystemEntity.__init__(self, db, id)
    (theme,) = db.FieldsForItem(
        id, AlbumItem.TABLE_NAME, 'theme')
    self.__theme = theme

  def type(self):
    return 'Album'

  def theme(self):
    return self.__theme

  def full_album_path(self, db):
    if self.parent_id():
      parent = AlbumItem(db, self.parent_id())
      return os.path.join((parent.full_album_path(db) or ''), self.path_component())
    else:
      return self.path_component()

class Derivative(object):
  TABLE_NAME = 'Derivative'

  def __init__(self, db, id):
    self.__id = id
    (source_id,operations) = db.FieldsForItem(id, Derivative.TABLE_NAME, 'derivativeSourceId', 'derivativeOperations')
    self.__source_id = None
    if source_id > 0:
      self.__source_id = source_id
    self.__operations = operations

  def source_id(self):
    return self.__source_id

  def operations(self):
    return self.__operations

class Comment(object):
  TABLE_NAME = 'Comment'

  def __init__(self, db, id):
    self.__id = id
    (subject,comment) = db.FieldsForItem(id, Comment.TABLE_NAME, 'subject', 'comment')
    self.__subject = subject
    self.__comment = comment

  def subject(self):
    return self.__subject

  def comment(self):
    return self.__comment

