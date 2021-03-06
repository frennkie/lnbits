import requests

from flask import abort, redirect, request, url_for
from lnurl import LnurlWithdrawResponse, handle as handle_lnurl
from lnurl.exceptions import LnurlException
from time import sleep

from lnbits.core import core_app
from lnbits.helpers import Status
from lnbits.settings import WALLET

from ..crud import create_account, get_user, create_wallet, create_payment


@core_app.route("/lnurlwallet")
def lnurlwallet():
    memo = "LNbits LNURL funding"

    try:
        withdraw_res = handle_lnurl(request.args.get("lightning"), response_class=LnurlWithdrawResponse)
    except LnurlException:
        abort(Status.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    try:
        ok, checking_id, payment_request, error_message = WALLET.create_invoice(withdraw_res.max_sats, memo)
    except Exception as e:
        ok, error_message = False, str(e)

    if not ok:
        abort(Status.INTERNAL_SERVER_ERROR, error_message)

    r = requests.get(
        withdraw_res.callback.base,
        params={**withdraw_res.callback.query_params, **{"k1": withdraw_res.k1, "pr": payment_request}},
    )

    if not r.ok:
        abort(Status.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    for i in range(10):
        invoice_status = WALLET.get_invoice_status(checking_id)
        sleep(i)
        if not invoice_status.paid:
            continue
        break

    user = get_user(create_account().id)
    wallet = create_wallet(user_id=user.id)
    create_payment(
        wallet_id=wallet.id,
        checking_id=checking_id,
        amount=withdraw_res.max_sats * 1000,
        memo=memo,
        pending=invoice_status.pending,
    )

    return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))
