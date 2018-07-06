import asyncio
import getpass

try:
    import readline
except ImportError:
    pass

import aioxmpp
import aioxmpp.ibr as ibr


async def get_fields(jid):
    metadata = aioxmpp.make_security_layer(None, no_verify=True)
    _, stream, features = await aioxmpp.node.connect_xmlstream(jid, metadata)
    reply = await ibr.get_registration_fields(stream)
    print(ibr.get_used_fields(reply))


async def get_info(jid, password):
    client = aioxmpp.PresenceManagedClient(
        jid,
        aioxmpp.make_security_layer(password, no_verify=True)
    )

    async with client.connected() as stream:
        service = ibr.RegistrationService(stream)
        reply = await service.get_client_info()
        print("Username: " + reply.username)


async def register(jid, password):
    metadata = aioxmpp.make_security_layer(None, no_verify=True)
    _, stream, features = await aioxmpp.node.connect_xmlstream(jid, metadata)

    query = ibr.Query(jid.localpart, password)
    await ibr.register(stream, query)
    print("Registered")


async def change_password(jid, old_password, new_password):
    client = aioxmpp.PresenceManagedClient(
        jid,
        aioxmpp.make_security_layer(old_password, no_verify=True)
    )

    async with client.connected() as stream:
        service = ibr.RegistrationService(stream)
        await service.change_pass(new_password)

    print("Password changed")


async def cancel(jid, password):
    client = aioxmpp.PresenceManagedClient(
        jid,
        aioxmpp.make_security_layer(password, no_verify=True)
    )

    async with client.connected() as stream:
        service = ibr.RegistrationService(stream)
        await service.cancel_registration()


if __name__ == "__main__":
    local_jid = aioxmpp.JID.fromstr(input("local JID> "))
    password = getpass.getpass()

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(cancel(local_jid, password))
    except:
        pass

    loop.run_until_complete(get_fields(local_jid, ))

    loop.run_until_complete(register(local_jid, password))

    loop.run_until_complete(get_info(local_jid, password))

    loop.run_until_complete(change_password(local_jid, password, "aaa"))

    try:
        loop.run_until_complete(cancel(local_jid, "aaa"))
    except:
        pass
