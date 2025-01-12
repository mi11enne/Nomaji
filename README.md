# Nomaji
This program converts audio metadata from their translated/transliterated versions back to the original. It works by looking up the album name on MusicBrainz and fetching the data from the original release. It converts the file name, track title, contributing artists and the album to their original versions. 

## How to use
Dump all the files and folders you want processed into the **Input** folder. Run main.py.

The program will automatically process all files if it finds a matching album with a matching artist on MusicBrainz. If the program fails to find your album, you can enter either the album name or the MusicBrainz ID of the release. Find the album on MusicBrainz and copy the UUID after https://musicbrainz.org/release/.

## Notes
The program will scan through all subfolders and sort the files by the album name. The files will be modified while retaining the original file structure. Folder names will not be changed.

The program will detect and process tracks from separate discs properly, as long as they are sorted into folders **Disc 1**, **Disc 2** or similar. It will also detect suffixes such as _(Disc 1)_ in the album name and disregard them while processing the files. 

The program will fail if the number of tracks on MusicBrainz doesn't match the number of files sharing the same album name. Make sure all the files that should belong to the same album share the same album name.
