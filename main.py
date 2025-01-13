import os
import sys
import musicbrainzngs
import re
from mutagen.easyid3 import EasyID3  # For MP3 metadata
from mutagen.flac import FLAC  # For FLAC metadata
from difflib import SequenceMatcher

# Configure MusicBrainz API
musicbrainzngs.set_useragent("AlbumMetadataUpdater", "1.0", "your_email@example.com")

def is_valid_release_id(input_str):
    """Check if the input string is a valid MusicBrainz release ID (UUID)."""
    uuid_regex = r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
    return re.match(uuid_regex, input_str.strip()) is not None

def clean_file_name(file_name):
    """Clean invalid symbols from file names and replace with suitable alternatives."""
    replacements = {
        '<': '(',
        '>': ')',
        ':': '-',
        '"': "'",
        '/': '-',
        '\\': '-',
        '|': '-',
        '?': '',
        '*': '',
    }

    # Replace invalid characters using the replacements dictionary
    cleaned_name = re.sub(
        r'[<>:"/\\|?*]', 
        lambda match: replacements.get(match.group(0), "_"), 
        file_name
    )
    return cleaned_name.strip()

def gather_all_files(base_folder):
    """Recursively gather all audio files from the base folder and subfolders."""
    audio_files = []
    for root, _, files in os.walk(base_folder):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav')):
                audio_files.append(os.path.join(root, file))
    return audio_files

def group_tracks_by_album(file_paths):
    """
    Group audio tracks by their album metadata and correctly assign disc numbers 
    based on file paths containing 'Disc 1', 'Disc 2', etc.
    """
    albums = {}

    # Regex to detect disc identifiers like 'Disc 1', 'CD 2', etc.
    disc_regex = re.compile(r'(Disc|CD)\s*(\d+)', re.IGNORECASE)

    for file_path in file_paths:
        try:
            if file_path.endswith('.mp3'):
                audio = EasyID3(file_path)
            elif file_path.endswith('.flac'):
                audio = FLAC(file_path)
            else:
                print(f"[WARNING] Skipping unsupported file type: {file_path}")
                continue

            album = audio.get('album', ["Unknown Album"])[0]

            disc_number = "1"  # Default to Disc 1 if no disc info is found
            disc_match = disc_regex.search(file_path)
            if disc_match:
                disc_number = disc_match.group(2)  # Extract the numeric disc number

            # Match and remove suffixes like (Disc 1), [Disc 2], etc.
            pattern = r"(\s*(\(|\[)?Disc (\d+)(\)|\])?)"
            match = re.search(pattern, album, re.IGNORECASE)
            if match:
                disc_number = match.group(3)  # Extract disc number
                album = re.sub(pattern, "", album).strip()  # Remove suffix

            if album not in albums:
                albums[album] = {}

            if disc_number not in albums[album]:
                albums[album][disc_number] = []

            albums[album][disc_number].append(file_path)

        except Exception as e:
            print(f"[ERROR] Failed to read metadata for {file_path}: {e}")
    return albums

def find_album_on_musicbrainz(album_name, artist_name=None):
    """Search for an album on MusicBrainz and return matches."""
    try:
        results = musicbrainzngs.search_releases(release=album_name, artist=artist_name, limit=10)
        return results.get("release-list", [])
    except musicbrainzngs.WebServiceError as e:
        print(f"[ERROR] MusicBrainz query failed: {e}")
        return []


def fetch_full_release_details(release_id):
    """Fetch full release details including track-list from MusicBrainz."""
    try:
        return musicbrainzngs.get_release_by_id(release_id, includes=["recordings", "media", "artist-credits", "release-groups"])
    except musicbrainzngs.WebServiceError as e:
        print(f"[ERROR] Failed to fetch release details for {release_id}: {e}")
        return None

def is_close_match(name1, name2, threshold=0.8):
    """Check if two names are close matches based on a similarity threshold."""
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio() >= threshold

def update_metadata(file_paths, track_metadata):
    """Update the metadata of audio files with the given track metadata."""
    # Sort files and metadata by track number
    sorted_tracks = sorted(
        zip(file_paths, track_metadata),
        key=lambda x: int(x[1].get("tracknumber", "0").split("/")[0])  # Sort by track number
    )
    
    for file_path, metadata in sorted_tracks:
        try:
            # print(f"\n[DEBUG] Processing file: {file_path}")
            if file_path.endswith('.mp3'):
                audio = EasyID3(file_path)
            elif file_path.endswith('.flac'):
                audio = FLAC(file_path)
            else:
                print(f"[WARNING] Skipping unsupported file type: {file_path}")
                continue

            # Fetch metadata values
            title = metadata.get("title", "Unknown")
            artist = metadata.get("artist", "Unknown")
            album = metadata.get("album", "Unknown")
            tracknumber = metadata.get("tracknumber", "0")
            date = metadata.get("date", "")

            # Log metadata being applied
           
            print(f"[DEBUG] Metadata fetched for this file:")
            print(f"        Track Number: {tracknumber}")
            print(f"        Title: {title}")
            print(f"        Artist: {artist}")
            print(f"        Album: {album}")
            print(f"        Date: {date}")
       

            # Update audio metadata
            audio["title"] = title
            audio["artist"] = artist
            # Only update the album if it is not "Unknown"
            if album != "Unknown Album":
                audio["album"] = album
            else:
                print(f"[INFO] Skipping album update for {file_path} as album is 'Unknown Album'")

            audio["tracknumber"] = tracknumber
            if date:
                audio["date"] = date
            audio.save()
            # print(f"[DEBUG] Metadata updated for: {file_path}")

            # Correctly extract and format the track number
            track_num = tracknumber.split("/")[0]
            if track_num.isdigit():
                track_num = track_num.zfill(2)  # Zero-pad track number
            else:
                print(f"[WARNING] Invalid track number '{tracknumber}', defaulting to 00.")
                track_num = "00"  # Default to 00 if invalid

            # Generate a filename based on metadata
            base_name = f"{track_num} - {title}"
            base_name = clean_file_name(base_name)  # Clean invalid characters
            ext = file_path.split('.')[-1]
            new_file_path = os.path.join(os.path.dirname(file_path), f"{base_name}.{ext}")

            # Safely rename the file
            if file_path != new_file_path:
                os.rename(file_path, new_file_path)
                # print(f"[INFO] Renamed file to {new_file_path}")
            else:
                # print(f"[INFO] Metadata updated without renaming for {file_path}")
                pass

        except Exception as e:
            print(f"[ERROR] Failed to update metadata for {file_path}: {e}")

def manual_input():
    user_input = input("Enter the correct album name or MusicBrainz ID manually or press Enter to skip: ").strip()
    if user_input:
        if is_valid_release_id(user_input):
            try:
                full_details = musicbrainzngs.get_release_by_id(
                    user_input, includes=["recordings", "media", "artist-credits", "release-groups"]
                )
                return full_details
            except musicbrainzngs.ResponseError as e:
                print(f"[ERROR] Failed to fetch release details: {e}")
                retry = input("Would you like to retry? (y/n): ").strip().lower()
                if retry != 'y':
                    return None
        else:
            matches = find_album_on_musicbrainz(user_input)
            if matches:
                selected_release = matches[0]
                release_id = selected_release.get("id")
                release_artist = selected_release.get("artist-credit", [{}])[0].get("artist", {}).get("name", "Unknown")
                
                try:
                    full_details = fetch_full_release_details(release_id)
                    print(f"[INFO] Using manually entered match: {selected_release.get('title')} by {release_artist}")
                    return full_details
                
                except musicbrainzngs.ResponseError as e:
                    print(f"[ERROR] Failed to fetch release details: {e}")
                    retry = input("Would you like to retry? (y/n): ").strip().lower()
                    if retry != 'y':
                        return None
                    
                return full_details
    else: 
        return

def main():
    input("Place files and folders to be processed in the Input folder. Press any key to continue.")

    # Get the directory of the executable or script
    if getattr(sys, 'frozen', False):  # Check if running as a PyInstaller-built executable
        script_directory = os.path.dirname(sys.executable)
    else:
        script_directory = os.path.dirname(os.path.abspath(__file__))

    folder = os.path.join(script_directory, "Input")

    if not os.path.exists(folder):
        print(f"[INFO] Creating missing 'Input' folder at: {folder}")
        os.makedirs(folder)

    all_files = gather_all_files(folder)
    albums = group_tracks_by_album(all_files)

    for album_name, discs in albums.items():
        print(f"[INFO] Processing album: {album_name}")
        artist_name = None

        # Safely get the first disc
        first_disc_key = next(iter(discs), None)
        if not first_disc_key:
            print(f"[WARNING] No discs found for album: {album_name}")
            continue

        try:
            # Safely get the first file in the first disc
            first_file = discs[first_disc_key][0] if discs[first_disc_key] else None
            if not first_file:
                print(f"[WARNING] No files found in Disc {first_disc_key} for album: {album_name}")
                continue

            # Extract metadata from the first file
            if first_file.endswith('.mp3'):
                audio = EasyID3(first_file)
            elif first_file.endswith('.flac'):
                audio = FLAC(first_file)
            else:
                print(f"[WARNING] Unsupported file type: {first_file}")
                continue

            artist_name = audio.get("artist", [None])[0]

        except Exception as e:
            print(f"[WARNING] Could not retrieve artist metadata: {e}")

        matches = find_album_on_musicbrainz(album_name, artist_name)

        for match in matches:
            release_id = match.get("id")
            release_title = match.get("title")
            release_artist = match.get("artist-credit", [{}])[0].get("artist", {}).get("name", "Unknown")
        
            if album_name == release_title and artist_name == release_artist:
                print(f"[INFO] Exact match found: {release_title} by {release_artist}")
                full_details = fetch_full_release_details(release_id)

            elif is_close_match(album_name, release_title):
                user_input = input(f"[PROMPT] Found a close match: {release_title} by {release_artist}. Use this? (y/n): ").strip().lower()
                if user_input == 'y':
                    full_details = fetch_full_release_details(release_id)
                
                else:
                    full_details = manual_input()
                
            else:
                print(f"[INFO] No match found for album: {album_name} by {artist_name}")
                full_details = manual_input()
    
            while full_details:
                mismatch = False
                media = {}
                release = full_details.get("release", {})
                album_name = release.get("release-group", {}).get("title", "Unknown Album")

                for medium in release.get("medium-list", []):
                    medium_number = medium.get("position", "1")
                    if medium_number not in media:
                        media[medium_number] = []

                    for track in medium.get("track-list", []):
                        media[medium_number].append({
                            "title": track.get("recording", {}).get("title", "Unknown"),
                            "artist": track.get("recording", {}).get("artist-credit", [{}])[0].get("artist", {}).get("name", "Unknown"),
                            "album": album_name,
                            "date": release.get("date", ""),
                            "tracknumber": track.get("position", "0"),  # Fetch the track number from the track data
                        })

                    if len(media) > len(discs):
                        print("[WARNING] Mismatch in disc count, verify that the correct release is selected.")
                        full_details = manual_input()
                        mismatch = True
                        break

                    if len(media[medium_number]) != len(discs[medium_number]):
                        print(f"[WARNING] Mismatch in track counts for Disc {medium_number}: {len(media[medium_number])} tracks in metadata vs {len(discs[medium_number])} files.")
                        full_details = manual_input()
                        mismatch = True
                        break

                if mismatch == False:
                    break

            else:
                break

            for medium_number, track_metadata in media.items():
                update_metadata(discs[medium_number], track_metadata)

            break

    input("End of program. Press any key to exit.")       
if __name__ == "__main__":
    main()