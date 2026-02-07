"""
Represented Objects are objects that have a presence in both the nif and Blender. They are
stored in a ReprObjectCollection, which provides fast lookup by blender object or nif
node."""

class ReprObject():
    """Object that is represented in both nif and Blender"""
    type = 'REPROBJ'
    
    def __init__(self, blender_obj=None, nifnode=None):
        self.blender_obj = blender_obj
        self.nifnode = nifnode

    @property
    def name(self):
        if self.blender_obj: return self.blender_obj.name
        return self.nifnode.name


class ReprObjectCollection():
    """Collection of represented objects. Adds dictionaries for fast lookup."""
    def __init__(self):
        self._collection = set()
        # Blender dict indexed by name
        self.blenderdict = {}
        # Need a separate dictionary for each file imported, indexed by filepath.
        self._filedict = {}

    def __len__(self):
        return len(self._collection)
    
    def __iter__(self):
        for ro in self._collection:
            yield ro


    @classmethod
    def New(cls, blender_objs=None):
        """
        Create a new ReprObjectCollection, optionally prefilled with the given blender objects.
        """
        roc = ReprObjectCollection()
        if blender_objs:
            for obj in blender_objs:
                roc.add(ReprObject(blender_obj=obj))
        return roc


    def add(self, reprobj):
        """
        Add a ReprObject to the collection. 
        """
        self._collection.add(reprobj)
        if reprobj.blender_obj:
            self.blenderdict[reprobj.blender_obj.name] = reprobj
        if reprobj.nifnode:
            fp = reprobj.nifnode.file.filepath
            if fp in self._filedict:
                d = self._filedict[fp]
            else:
                self._filedict[fp] = {}
                d = self._filedict[fp]
            d[reprobj.nifnode.id] = reprobj


    def add_pair(self, obj, nifnode):
        self.add(ReprObject(obj, nifnode))


    def remove(self, obj):
        """
        Remove obj from the collection. May be a ReprObject, blender object, or nif node.
        """
        if isinstance(obj, ReprObject):
            self._collection.remove(obj)
            del self.blenderdict[obj.blender_obj.name]
            for fp, fd in self._filedict.items():
                if obj.nifnode and obj.nifnode.id in fd:
                    del fd[obj.nifnode.id]
        else:
            matches = [x for x in self._collection if x.blender_obj == obj or x.nifnode == obj]
            for ro in matches:
                self._collection.remove(ro)
                if ro.blender_obj and ro.blender_obj.name in self.blenderdict:
                    del self.blenderdict[ro.blender_obj.name]
                if ro.nifnode:
                    fp = ro.nifnode.file.filepath
                    if fp in self._filedict:
                        d = self._filedict[fp]
                        if ro.nifnode.id in d:
                            del d[ro.nifnode.id]


    def find_nifnode(self, nifnode):
        fp = nifnode.file.filepath
        if fp in self._filedict:
            d = self._filedict[fp]
            if nifnode.id in d:
                return d[nifnode.id]
        return None


    def find_blend(self, blendobj):
        """
        Find a blender object in the collection.
        """
        if blendobj.name in self.blenderdict: 
            return self.blenderdict[blendobj.name]
        return None


    def find_nifname(self, nif, name):
        for reprobj in self._collection:
            if reprobj.nifnode \
                and reprobj.nifnode.file == nif \
                and reprobj.nifnode.name == name: 
                return reprobj
        return None


    def blender_objects(self):
        for ro in self._collection:
            if ro.blender_obj:
                yield ro.blender_obj
    

