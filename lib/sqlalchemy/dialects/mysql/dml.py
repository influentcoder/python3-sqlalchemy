from ...sql.elements import ClauseElement
from ...sql.dml import Insert as StandardInsert
from ...sql.expression import alias
from ...util.langhelpers import public_factory
from ...sql.base import _generative
from ... import exc
from ... import util

__all__ = ('Insert', 'insert')


class Insert(StandardInsert):
    """MySQL-specific implementation of INSERT.

    Adds methods for MySQL-specific syntaxes such as ON DUPLICATE KEY UPDATE.

    .. versionadded:: 1.2

    """

    @property
    def inserted(self):
        """Provide the "inserted" namespace for an ON DUPLICATE KEY UPDATE statement

        MySQL's ON DUPLICATE KEY UPDATE clause allows reference to the row
        that would be inserted, via a special function called ``VALUES()``.
        This attribute provides all columns in this row to be referenaceable
        such that they will render within a ``VALUES()`` function inside the
        ON DUPLICATE KEY UPDATE clause.    The attribute is named ``.inserted``
        so as not to conflict with the existing :meth:`.Insert.values` method.

        .. seealso::

            :ref:`mysql_insert_on_duplicate_key_update` - example of how
            to use :attr:`.Insert.inserted`

        """
        return self.inserted_alias.columns

    @util.memoized_property
    def inserted_alias(self):
        return alias(self.table, name='inserted')

    @_generative
    def on_duplicate_key_update(self, *args, **kw):
        r"""
        Specifies the ON DUPLICATE KEY UPDATE clause.

        :param \**kw:  Column keys linked to UPDATE values.  The
         values may be any SQL expression or supported literal Python
         values.

        .. warning:: This dictionary does **not** take into account
           Python-specified default UPDATE values or generation functions,
           e.g. those specified using :paramref:`.Column.onupdate`.
           These values will not be exercised for an ON DUPLICATE KEY UPDATE
           style of UPDATE, unless values are manually specified here.

        :param \*args: As an alternative to passing key/value parameters,
         a dictionary or list of 2-tuples can be passed as a single positional
         argument.

         Passing a single dictionary is equivalent to the keyword argument
         form::

            insert().on_duplicate_key_update({"name": "some name"})

         Passing a list of 2-tuples indicates that the parameter assignments
         in the UPDATE clause should be ordered as sent, in a manner similar
         to that described for the :class:`.Update` contruct overall
         in :ref:`updates_order_parameters`::

            insert().on_duplicate_key_update(
                [("name": "some name"), ("value", "some value")])

         .. versionchanged:: 1.3 parameters can be specified as a dictionary
            or list of 2-tuples; the latter form provides for parameter
            ordering.


        .. versionadded:: 1.2

        .. seealso::

            :ref:`mysql_insert_on_duplicate_key_update`

        """
        if args and kw:
            raise exc.ArgumentError(
                "Can't pass kwargs and positional arguments simultaneously")

        if args:
            if len(args) > 1:
                raise exc.ArgumentError(
                    "Only a single dictionary or list of tuples "
                    "is accepted positionally.")
            values = args[0]
        else:
            values = kw

        inserted_alias = getattr(self, 'inserted_alias', None)
        self._post_values_clause = OnDuplicateClause(inserted_alias, values)
        return self


insert = public_factory(Insert, '.dialects.mysql.insert')


class OnDuplicateClause(ClauseElement):
    __visit_name__ = 'on_duplicate_key_update'

    _parameter_ordering = None

    def __init__(self, inserted_alias, update):
        self.inserted_alias = inserted_alias

        # auto-detect that parameters should be ordered.   This is copied from
        # Update._proces_colparams(), however we don't look for a special flag
        # in this case since we are not disambiguating from other use cases as
        # we are in Update.values().
        if isinstance(update, list) and \
                (update and isinstance(update[0], tuple)):
            self._parameter_ordering = [key for key, value in update]
            update = dict(update)

        if not update or not isinstance(update, dict):
            raise ValueError('update parameter must be a non-empty dictionary')
        self.update = update
