! Flyby search: the fitness of a trajectory with deep-space manoeuvres (pykep's mga_1dsm in the direct encoding, plus the
! parking-orbit burns of flyby/routes3.py), compiled and called through ctypes. Positions come from tables with cubic Hermite
! interpolation. Decision vector: t0, u, v, Vinf, eta1, T1, then beta, rp, eta, T per further leg.
module flyby_fit
  use iso_c_binding
  use iso_fortran_env, only: wp => real64
  use lambert_izzo, only: solve_lambert_izzo
  implicit none
  real(wp), parameter :: out_of_range = 999.0_wp, day_s = 86400.0_wp, pi_ = acos(-1.0_wp)
contains
  logical function eph(tab, nt, t0, h, t, r, v)     ! tab [6, nt]: m and m/s; t0, h, t in days
    integer, intent(in) :: nt
    real(wp), intent(in) :: tab(6, nt), t0, h, t
    real(wp), intent(out) :: r(3), v(3)
    real(wp) :: s, x, h00, h10, h01, h11, d00, d10, d01, d11, hs
    integer :: i
    s = (t - t0) / h; eph = .false.
    if (s < 0.0_wp .or. s > real(nt - 1, wp)) return
    i = min(int(s), nt - 2); x = s - i; hs = h * day_s
    h00 = (1 + 2 * x) * (1 - x) ** 2; h10 = x * (1 - x) ** 2; h01 = x * x * (3 - 2 * x); h11 = x * x * (x - 1)
    d00 = 6 * x * (x - 1); d10 = (1 - x) * (1 - 3 * x); d01 = -d00; d11 = x * (3 * x - 2)
    r = h00 * tab(1:3, i + 1) + h10 * hs * tab(4:6, i + 1) + h01 * tab(1:3, i + 2) + h11 * hs * tab(4:6, i + 2)
    v = (d00 * tab(1:3, i + 1) + d10 * hs * tab(4:6, i + 1) + d01 * tab(1:3, i + 2) + d11 * hs * tab(4:6, i + 2)) / hs
    eph = .true.
  end function

  pure subroutine propagate(r0, v0, dt, mu, r, v, ok)     ! two-body, universal variable, Newton inside a bracket
    real(wp), intent(in) :: r0(3), v0(3), dt, mu
    real(wp), intent(out) :: r(3), v(3)
    logical, intent(out) :: ok
    real(wp) :: rn, vr, alpha, chi, sq, z, c2, c3, f, df, lo, hi, nw, rr, ff, gg, fd, gd
    integer :: it
    rn = norm2(r0); vr = dot_product(r0, v0) / rn; alpha = 2.0_wp / rn - dot_product(v0, v0) / mu; sq = sqrt(mu); ok = .false.
    lo = 0.0_wp; hi = huge(1.0_wp); chi = sq * abs(alpha) * dt
    if (alpha <= 0.0_wp) chi = sq * dt / rn
    do it = 1, 100
      z = alpha * chi * chi; call stumpff(z, c2, c3)
      f = rn * vr / sq * chi * chi * c2 + (1.0_wp - alpha * rn) * chi ** 3 * c3 + rn * chi - sq * dt
      df = rn * vr / sq * chi * (1.0_wp - z * c3) + (1.0_wp - alpha * rn) * chi * chi * c2 + rn
      if (f > 0.0_wp) then
        hi = chi
      else
        lo = chi
      end if
      nw = chi - f / df
      if (.not. (nw > lo .and. nw < hi)) then
        nw = merge(0.5_wp * (lo + hi), 2.0_wp * chi + 1.0_wp, hi < huge(1.0_wp))
      end if
      if (abs(nw - chi) <= 1.0e-13_wp * max(1.0_wp, abs(chi))) then
        chi = nw; ok = .true.; exit
      end if
      chi = nw
    end do
    z = alpha * chi * chi; call stumpff(z, c2, c3)
    ff = 1.0_wp - chi * chi / rn * c2; gg = dt - chi ** 3 / sq * c3
    r = ff * r0 + gg * v0; rr = norm2(r)
    fd = sq / (rr * rn) * chi * (z * c3 - 1.0_wp); gd = 1.0_wp - chi * chi / rr * c2
    v = fd * r0 + gd * v0
  end subroutine

  pure subroutine stumpff(z, c2, c3)
    real(wp), intent(in) :: z
    real(wp), intent(out) :: c2, c3
    real(wp) :: s
    if (z > 1.0e-6_wp) then
      s = sqrt(z); c2 = (1.0_wp - cos(s)) / z; c3 = (s - sin(s)) / (s * z)
    else if (z < -1.0e-6_wp) then
      s = sqrt(-z); c2 = (cosh(s) - 1.0_wp) / (-z); c3 = (sinh(s) - s) / (s * (-z))
    else
      c2 = 0.5_wp - z / 24.0_wp; c3 = 1.0_wp / 6.0_wp - z / 120.0_wp
    end if
  end subroutine

  pure function cross3(a, b) result(c)
    real(wp), intent(in) :: a(3), b(3)
    real(wp) :: c(3)
    c = [a(2) * b(3) - a(3) * b(2), a(3) * b(1) - a(1) * b(3), a(1) * b(2) - a(2) * b(1)]
  end function

  pure function fb_vout(vin, vpla, rp, beta, mu) result(vout)
    real(wp), intent(in) :: vin(3), vpla(3), rp, beta, mu
    real(wp) :: vout(3), vr(3), n, e, delta, i(3), j(3), k(3)
    vr = vin - vpla; n = norm2(vr); e = 1.0_wp + rp / mu * n * n; delta = 2.0_wp * asin(1.0_wp / e)
    i = vr / n; j = cross3(i, vpla); j = j / norm2(j); k = cross3(i, j)
    vout = vpla + n * cos(delta) * i + n * cos(beta) * sin(delta) * j + n * sin(beta) * sin(delta) * k
  end function

  pure real(wp) function burn(v, m, r)                    ! km/s; m = 0: rendezvous
    real(wp), intent(in) :: v, m, r
    if (m > 0.0_wp) then
      burn = sqrt(v * v + 2.0_wp * m / r) - sqrt(m / r)
    else
      burn = v
    end if
  end function

  ! the fitness of nb decision vectors; out(1, b) = total km/s (999 outside the tables), out(2, b) = DSMs, out(3, b) = arrival excess speed
  subroutine flyby_fitness(nseq, nx, nb, x, tab, off, nt, tstart, h, mu_self, radius, pm0, pr0, pm1, pr1, aero, vlim, trim, mu_sun, out) &
      bind(c, name='flyby_fitness')
    integer(c_int), value :: nseq, nx, nb, aero
    real(c_double), intent(in) :: x(nx, nb), tab(*), tstart(nseq), h(nseq), mu_self(nseq), radius(nseq)
    integer(c_int), intent(in) :: off(nseq), nt(nseq)
    real(c_double), value :: pm0, pr0, pm1, pr1, vlim, trim, mu_sun
    real(c_double), intent(out) :: out(3, nb)
    real(wp) :: t, T_i, eta, theta, phi, vinf(3), rpl(3, nseq), vpl(3, nseq), r(3), v(3), dsm, vout(3), va, cost, rpf, beta
    real(wp), allocatable :: w1(:,:), w2(:,:)
    integer :: b, i, l
    logical :: ok, lw
    batch: do b = 1, nb
      out(:, b) = [out_of_range, out_of_range, out_of_range]
      t = x(1, b)
      do i = 1, nseq
        if (.not. eph(tab(off(i) + 1), nt(i), tstart(i), h(i), t, rpl(:, i), vpl(:, i))) cycle batch
        if (i < nseq) t = t + x(6 + 4 * (i - 1), b)
      end do
      theta = 2.0_wp * pi_ * x(2, b); phi = acos(2.0_wp * x(3, b) - 1.0_wp) - pi_ / 2.0_wp
      vinf = x(4, b) * [cos(phi) * cos(theta), cos(phi) * sin(theta), sin(phi)]
      dsm = 0.0_wp; vout = vpl(:, 1) + vinf
      do l = 1, nseq - 1
        if (l == 1) then
          eta = x(5, b)
        else
          rpf = x(8 + 4 * (l - 2), b) * radius(l); beta = x(7 + 4 * (l - 2), b); eta = x(9 + 4 * (l - 2), b)
          vout = fb_vout(w2(:, 1), vpl(:, l), rpf, beta, mu_self(l))
        end if
        T_i = x(6 + 4 * (l - 1), b)
        call propagate(rpl(:, l), vout, eta * T_i * day_s, mu_sun, r, v, ok)
        if (.not. ok) cycle batch
        lw = r(1) * rpl(2, l + 1) - r(2) * rpl(1, l + 1) < 0.0_wp
        call solve_lambert_izzo(r, rpl(:, l + 1), (1.0_wp - eta) * T_i * day_s, mu_sun, lw, 0, w1, w2, ok)
        if (.not. ok) cycle batch
        dsm = dsm + norm2(w1(:, 1) - v)
      end do
      dsm = dsm / 1000.0_wp; va = norm2(w2(:, 1) - vpl(:, nseq)) / 1000.0_wp
      if (aero /= 0) then
        cost = merge(burn(va, pm1, pr1) - burn(vlim, pm1, pr1), 0.0_wp, va > vlim) + trim
      else
        cost = burn(va, pm1, pr1)
      end if
      out(:, b) = [burn(x(4, b) / 1000.0_wp, pm0, pr0) + dsm + cost, dsm, va]
    end do batch
  end subroutine
end module
