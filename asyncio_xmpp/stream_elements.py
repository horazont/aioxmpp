from .stanza_props import *
from .utils import etree, namespaces, split_tag
from .xml import lookup

class StreamFeatures(etree.ElementBase):
    TAG = "{{{}}}features".format(namespaces.xmlstream)

    def get_features(self):
        for el in self:
            yield (el.tag, el)

    def get_feature_dict(self):
        return dict(self.get_features)

    def get_feature(self, tag):
        return self.find(tag)

    def require_feature(self, tag):
        result = self.get_feature(tag)
        if result is None:
            raise KeyError(tag)
        return result

ns_stream = lookup.get_namespace(namespaces.xmlstream)
ns_stream["features"] = StreamFeatures
del ns_stream
