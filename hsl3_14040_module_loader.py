#
# hsl3_module_loader - side-load python modules from HLSZ files
#   Written by Ralf Dragon <hypnotoad@lindra.de>
#   Copyright (C) 2026 Ralf Dragon
#
# This program is freely distributable per the following license:
#
#  Permission to use, copy, modify, and distribute this software and its
#  documentation for any purpose and without fee is hereby granted,
#  provided that the above copyright notice appears in all copies and that
#  both that copyright notice and this permission notice appear in
#  supporting documentation.
#
#  I DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING ALL
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO EVENT SHALL I
#  BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY
#  DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
#  WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
#  ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
#  SOFTWARE.

import sys
from urllib.request import urlretrieve
import logging

class ModuleLoader:
    def __init__(self, hsl3):
        self.fw = hsl3
        self.is_mock = hasattr(self.fw, "is_mock")
    
    def load_zip(self, module_name, file_name, root_folder=""):
        # load the module $module_name residing in the zip file
        # $file_name at the location $root_folder. The zip file has to
        # be placed into the folder $module_id/hsupload in the hslz
        # file.
        if not self.is_mock:
            local_zip_path = file_name
            url = "http://127.0.0.1:65000/logic/{}/{}".format(self.fw.get_module_id(), file_name)
            local_filename, headers = urlretrieve(url, local_zip_path)
        else:
            local_zip_path = "{}/hsupload/{}".format(self.fw.get_module_id(), file_name)
            
        sys.path.insert(0, local_zip_path + root_folder)

        __import__(module_name)
        
