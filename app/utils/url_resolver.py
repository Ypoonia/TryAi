#!/usr/bin/env python3
from typing import Optional


class UrlResolver:
   

    @staticmethod
    def to_public(internal_url: str) -> str:
       
        if not internal_url:
            return internal_url
            
        if internal_url.startswith("file://"):
       
            file_path = internal_url.replace("file://", "")
            filename = file_path.split("/")[-1]  # Get last part of path
            
    
            if filename.endswith(".json"):
                filename = filename.replace(".json", ".csv")
                
            return f"/files/reports/{filename}"
        
     
        return internal_url
