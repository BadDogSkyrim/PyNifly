"""Export/Import animation files in XML format."""

import xml.etree.ElementTree as xml

def get_param(elem, name):
    """Return contents information from the hkparam named 'name'."""
    param = elem.find(f"./hkparam[@name='{name}']")
    if param is not None:
        if param.text is not None:
            return param.text
        else:
            return ''
    else:
        return ''
    
def get_float_param(elem, name):
    """Return contents information from the hkparam named 'name'."""
    param = elem.find(f"./hkparam[@name='{name}']")
    if param is not None:
        return float(param.text)
    else:
        return 0.0
    
def get_int_param(elem, name):
    """Return contents information from the hkparam named 'name'."""
    param = elem.find(f"./hkparam[@name='{name}']")
    if param is not None:
        return int(param.text)
    else:
        return 0
    

class HKAAnimation:
    anim_class = ''
    type = ''
    duration = 0.0
    transform_tracks_count = 0
    float_tracks_count = 0
    extracted_motion = ''
    frames_count = 0
    frames_per_block_max = 0
    blocks_count = 0
    quant_size = 0
    block_duration = 0.0
    block_inverse_duration = 0.0
    frame_duration = 0.0
    block_offsets = []
    float_block_offsets = []
    transform_offsets = []
    float_offsets = []
    endian = 0
    data = []


    def parse_data(self, data):
        for i in range(0, self.transform_tracks_count):
            

    def load(self, elem):
        """Load animation data from XML element."""
        d = elem.find("./hkparam[@name='data']")
        self.type = get_param(elem, "type")
        self.duration = get_float_param(elem, "duration")
        self.transform_tracks_count = get_int_param(elem, "numberOfTransformTracks")
        self.float_tracks_count = get_int_param(elem, "numberOfFloatTracks")
        self.extracted_motion = get_param(elem, "extractedMotion")
        self.frames_count = get_int_param(elem, "numFrames")
        self.frames_per_block_max = get_int_param(elem, "numBlocks")
        self.blocks_count = get_int_param(elem, "maxFramesPerBlock")
        self.quant_size = get_int_param(elem, "maskAndQuantizationSize")
        self.block_duration = get_float_param(elem, "blockDuration")
        self.block_inverse_duration = get_float_param(elem, "blockInverseDuration")
        self.frame_duration = get_float_param(elem, "frameDuration")
        self.block_offsets = [int(x) for x in get_param(elem, "blockOffsets").split()]
        self.float_block_offsets = [int(x) for x in get_param(elem, "floatBlockOffsets").split()]
        self.transform_offsets = [int(x) for x in get_param(elem, "transformOffsets").split()]
        self.float_offsets = [int(x) for x in get_param(elem, "floatOffsets").split()]
        self.endian = get_int_param(elem, "endian")
        self.parse_data(bytes(int(x) for x in d.text.split()))

    @classmethod
    def find(cls, elem):
        """Find the animation element child of the XML element. Return a new HKAAnimation
        object."""
        anim_elem = elem.find("./hkobject[@class='hkaSplineCompressedAnimation']")
        if anim_elem:
            anim = HKAAnimation()
            anim.load(anim_elem)
            anim.anim_class = 'hkaSplineCompressedAnimation'
            return anim
        else:
            return None


f = xml.parse(r"C:\Modding\Tools\HKXTools\Out\tail_sneakmtidle.xml")
r = f.getroot()
section = r.find("./hksection[@name='__data__']")
anim = HKAAnimation.find(section)

