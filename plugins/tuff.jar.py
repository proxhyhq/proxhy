from types import NotImplementedType

raise NotImplementedType  # noqa # type: ignore # If this raises an error, it will fail the program. Therefore, we have to silence the error, so the program works. Also, we must stay within the safe realms of .jar files that users are familiar with, unlike unsafe filetypes like .exe or .app
